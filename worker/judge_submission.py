from dataclasses import dataclass
from pathlib import Path
import shutil
import subprocess

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.config import settings
from app.db import SessionLocal
from app.languages import get_language
from app.languages.types import LanguageSpec
from app.models import Problem, Submission, Testcase
from app.problem_assets import checker_binary_path
from worker.isolate_runner import (
    IsolateBox,
    IsolateResult,
    IsolateUnavailableError,
    copy_into_box,
    copy_box_contents_to_directory,
    copy_tree_into_box,
    isolate_box,
    restore_box_contents_from_directory,
    run_in_box,
)


BOX_WORK_DIR = Path("/box")


@dataclass(frozen=True)
class PreparedSubmission:
    submission_id: int
    source_code: str
    language_key: str
    work_directory: Path
    problem: Problem
    testcases: list[Testcase]


@dataclass(frozen=True)
class JudgeOutcome:
    status: str
    details: str
    execution_time_ms: int | None = None
    memory_usage_kb: int | None = None
    score: int | None = None
    max_score: int | None = None


@dataclass(frozen=True)
class CheckerOutcome:
    status: str
    details: str


@dataclass
class SubtaskProgress:
    subtask_id: str
    score: int
    cases: list[int]
    passed: bool = True
    failure_status: str | None = None
    failure_details: str | None = None


def update_submission_status(
    submission_id: int,
    status: str,
    details: str | None = None,
    execution_time_ms: int | None = None,
    memory_usage_kb: int | None = None,
    score: int | None = None,
    max_score: int | None = None,
) -> None:
    with SessionLocal() as db:
        submission = db.get(Submission, submission_id)
        if not submission:
            return
        submission.status = status
        submission.details = details
        submission.execution_time_ms = execution_time_ms
        submission.memory_usage_kb = memory_usage_kb
        submission.score = score
        submission.max_score = max_score
        db.commit()


def summarize_stderr(result: IsolateResult) -> str:
    detail = result.stderr or result.sandbox_stderr
    return detail.decode("utf-8", errors="replace").strip()[:4000]


def execution_metrics(result: IsolateResult) -> tuple[int | None, int | None]:
    time_ms = result.time_ms or result.wall_time_ms
    memory_kb = result.memory_kb
    return time_ms, memory_kb


def is_memory_limit_exceeded(result: IsolateResult) -> bool:
    message = (result.meta.get("message") or "").lower()
    return result.meta.get("cg-oom-killed") == "1" or "memory" in message


def load_submission_for_judging(submission_id: int) -> PreparedSubmission | None:
    with SessionLocal() as db:
        submission = db.scalar(
            select(Submission)
            .where(Submission.id == submission_id)
            .options(selectinload(Submission.problem).selectinload(Problem.testcases))
        )
        if not submission:
            return None

        problem = submission.problem
        testcases = sorted(problem.testcases, key=lambda tc: tc.order_index)
        work_directory = Path(settings.data_dir) / "submissions" / f"{submission_id}"
        return PreparedSubmission(
            submission_id=submission.id,
            source_code=submission.source_code,
            language_key=submission.language,
            work_directory=work_directory,
            problem=problem,
            testcases=testcases,
        )


def prepare_work_directory(work_directory: Path) -> None:
    if work_directory.exists():
        shutil.rmtree(work_directory)
    work_directory.mkdir(parents=True, exist_ok=True)


def write_source_file(work_directory: Path, source_filename: str, content: str) -> Path:
    source_path = work_directory / source_filename
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_text(content, encoding="utf-8")
    return source_path


def compiled_snapshot_directory(box: IsolateBox) -> Path:
    return box.root_dir / "compiled-box"


def remove_box_path(box: IsolateBox, target_name: str) -> None:
    target_path = box.root_dir / "box" / target_name
    if not target_path.exists() and not target_path.is_symlink():
        return
    if target_path.is_dir() and not target_path.is_symlink():
        shutil.rmtree(target_path)
    else:
        target_path.unlink()


def remove_compile_outputs(box: IsolateBox) -> None:
    remove_box_path(box, "compile_stdout.txt")
    remove_box_path(box, "compile_stderr.txt")


def apply_outcome(submission_id: int, outcome: JudgeOutcome) -> None:
    update_submission_status(
        submission_id,
        outcome.status,
        outcome.details,
        outcome.execution_time_ms,
        outcome.memory_usage_kb,
        outcome.score,
        outcome.max_score,
    )


def compile_submission(box: IsolateBox, language: LanguageSpec) -> JudgeOutcome | None:
    compile_command = language.render_compile_command(BOX_WORK_DIR)
    if compile_command is None:
        return None

    result = run_in_box(
        box,
        compile_command,
        time_limit_ms=language.compile_timeout_seconds * 1000,
        wall_time_ms=(language.compile_timeout_seconds + 1) * 1000,
        memory_limit_mb=settings.default_memory_limit_mb,
        process_limit=language.compile_process_limit,
        stdout_name="compile_stdout.txt",
        stderr_name="compile_stderr.txt",
        env=["PATH=/usr/bin:/bin"],
    )

    if result.returncode != 0 or result.status in {"TO", "RE", "SG", "XX"}:
        details = summarize_stderr(result) or "Compilation failed"
        if result.status == "TO":
            details = "Compilation timed out"
        elif is_memory_limit_exceeded(result):
            details = "Compilation exceeded memory limit"
        return JudgeOutcome(status="CE", details=details)
    return None


def stage_testcase_input(box: IsolateBox, testcase: Testcase) -> None:
    input_path = Path(testcase.input_path)
    if not input_path.exists():
        raise RuntimeError(f"Missing testcase input file: {input_path}")
    copy_into_box(box, input_path, "input.txt")


def checker_message(result: subprocess.CompletedProcess[str]) -> str:
    return (result.stderr or result.stdout).strip()[:4000]


def run_checker(
    problem: Problem,
    testcase: Testcase,
    output_path: Path,
    *,
    subtask_id: str | None = None,
) -> CheckerOutcome:
    input_path = Path(testcase.input_path)
    answer_path = Path(testcase.output_path)
    checker_path = checker_binary_path(problem.id)

    if not checker_path.exists():
        raise RuntimeError(f"Missing checker binary: {checker_path}")
    if not answer_path.exists():
        raise RuntimeError(f"Missing testcase output file: {answer_path}")

    command = [str(checker_path), str(input_path), str(output_path), str(answer_path)]
    if subtask_id is not None:
        command.extend(["--group", str(subtask_id)])

    try:
        result = subprocess.run(command, check=False, capture_output=True, text=True, timeout=5)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"Checker timed out for testcase {testcase.order_index}") from exc

    detail = checker_message(result)
    if result.returncode == 0:
        return CheckerOutcome(status="AC", details=detail or f"Accepted testcase {testcase.order_index}")
    if result.returncode in {1, 2} or result.returncode >= 50:
        return CheckerOutcome(status="WA", details=detail or f"Wrong answer on testcase {testcase.order_index}")
    return CheckerOutcome(status="RE", details=detail or f"Checker failed on testcase {testcase.order_index}")


def judge_testcase(
    box: IsolateBox,
    language: LanguageSpec,
    testcase: Testcase,
    problem: Problem,
) -> JudgeOutcome:
    result = run_in_box(
        box,
        language.render_run_command(BOX_WORK_DIR),
        time_limit_ms=problem.time_limit_ms,
        wall_time_ms=problem.time_limit_ms + 1000,
        memory_limit_mb=problem.memory_limit,
        process_limit=language.run_process_limit,
        stdin_name="input.txt",
        stdout_name="output.txt",
    )
    execution_time_ms, memory_usage_kb = execution_metrics(result)

    if result.status == "TO":
        return JudgeOutcome(
            status="TLE",
            details=f"Time limit exceeded on testcase {testcase.order_index}",
            execution_time_ms=execution_time_ms,
            memory_usage_kb=memory_usage_kb,
        )

    if is_memory_limit_exceeded(result):
        return JudgeOutcome(
            status="MLE",
            details=f"Memory limit exceeded on testcase {testcase.order_index}",
            execution_time_ms=execution_time_ms,
            memory_usage_kb=memory_usage_kb,
        )

    if result.returncode != 0 or result.status in {"RE", "SG", "XX"}:
        detail = summarize_stderr(result) or f"Runtime error on testcase {testcase.order_index}"
        return JudgeOutcome(
            status="RE",
            details=detail,
            execution_time_ms=execution_time_ms,
            memory_usage_kb=memory_usage_kb,
        )

    if not problem.use_subtask:
        checker_outcome = run_checker(
            problem,
            testcase,
            box.root_dir / "box" / "output.txt",
        )
        if checker_outcome.status != "AC":
            return JudgeOutcome(
                status=checker_outcome.status,
                details=checker_outcome.details,
                execution_time_ms=execution_time_ms,
                memory_usage_kb=memory_usage_kb,
            )
        detail = checker_outcome.details
    else:
        detail = f"Executed testcase {testcase.order_index}"

    return JudgeOutcome(
        status="AC",
        details=detail,
        execution_time_ms=execution_time_ms,
        memory_usage_kb=memory_usage_kb,
    )


def finalize_success(
    submission_id: int,
    testcase_count: int,
    max_execution_time_ms: int,
    max_memory_usage_kb: int,
) -> None:
    update_submission_status(
        submission_id,
        "AC",
        f"Accepted ({testcase_count} testcases)",
        max_execution_time_ms or None,
        max_memory_usage_kb or None,
        100,
        100,
    )


def subtask_cases(problem: Problem, testcase_order_index: int) -> list[str]:
    matching_subtasks: list[str] = []
    for subtask_id, info in (problem.subtask_info or {}).items():
        cases = info.get("cases") or []
        if testcase_order_index in cases:
            matching_subtasks.append(str(subtask_id))
    return matching_subtasks


def parse_subtasks(problem: Problem) -> list[SubtaskProgress]:
    parsed: list[SubtaskProgress] = []
    for subtask_id, info in sorted(
        (problem.subtask_info or {}).items(),
        key=lambda item: int(item[0]) if str(item[0]).isdigit() else str(item[0]),
    ):
        parsed.append(
            SubtaskProgress(
                subtask_id=str(subtask_id),
                score=int(info.get("score", 0)),
                cases=[int(case_id) for case_id in (info.get("cases") or [])],
            )
        )
    return parsed


def failure_priority(status: str) -> int:
    return {
        "RE": 0,
        "TLE": 1,
        "MLE": 2,
        "WA": 3,
    }.get(status, 4)


def finalize_subtask_outcome(
    submission_id: int,
    subtasks: list[SubtaskProgress],
    max_execution_time_ms: int,
    max_memory_usage_kb: int,
) -> None:
    max_score = sum(subtask.score for subtask in subtasks)
    earned_score = sum(subtask.score for subtask in subtasks if subtask.passed)
    failures = [subtask for subtask in subtasks if not subtask.passed]

    if earned_score == max_score:
        status = "AC"
    elif earned_score > 0:
        status = "PAC"
    elif failures:
        status = min(failures, key=lambda subtask: failure_priority(subtask.failure_status or "WA")).failure_status or "WA"
    else:
        status = "WA"

    lines = [f"Score: {earned_score}/{max_score}"]
    for subtask in subtasks:
        if subtask.passed:
            lines.append(f"Subtask {subtask.subtask_id}: AC (+{subtask.score})")
        else:
            lines.append(
                f"Subtask {subtask.subtask_id}: {subtask.failure_status or 'WA'} ({subtask.failure_details or 'failed'})"
            )

    update_submission_status(
        submission_id,
        status,
        "\n".join(lines),
        max_execution_time_ms or None,
        max_memory_usage_kb or None,
        earned_score,
        max_score,
    )


def judge_submission(submission_id: int) -> None:
    prepared = load_submission_for_judging(submission_id)
    if prepared is None:
        return

    update_submission_status(submission_id, "JUDGING", "Preparing execution")
    try:
        language = get_language(prepared.language_key)
    except ValueError as exc:
        update_submission_status(submission_id, "CE", str(exc))
        return

    try:
        prepare_work_directory(prepared.work_directory)
        write_source_file(prepared.work_directory, language.source_filename, prepared.source_code)

        with isolate_box() as box:
            copy_tree_into_box(box, prepared.work_directory)

            compile_outcome = compile_submission(box, language)
            if compile_outcome is not None:
                apply_outcome(submission_id, compile_outcome)
                return

            remove_compile_outputs(box)
            snapshot_dir = compiled_snapshot_directory(box)
            copy_box_contents_to_directory(box, snapshot_dir)

            max_execution_time_ms = 0
            max_memory_usage_kb = 0
            subtasks = parse_subtasks(prepared.problem) if prepared.problem.use_subtask else []
            subtask_by_id = {subtask.subtask_id: subtask for subtask in subtasks}

            for testcase in prepared.testcases:
                restore_box_contents_from_directory(box, snapshot_dir)
                stage_testcase_input(box, testcase)
                outcome = judge_testcase(
                    box,
                    language,
                    testcase,
                    prepared.problem,
                )
                max_execution_time_ms = max(max_execution_time_ms, outcome.execution_time_ms or 0)
                max_memory_usage_kb = max(max_memory_usage_kb, outcome.memory_usage_kb or 0)
                if not prepared.problem.use_subtask and outcome.status != "AC":
                    apply_outcome(submission_id, outcome)
                    return
                if not prepared.problem.use_subtask:
                    continue

                testcase_subtasks = subtask_cases(prepared.problem, testcase.order_index)
                if outcome.status != "AC":
                    for subtask_id in testcase_subtasks:
                        subtask = subtask_by_id[subtask_id]
                        if subtask.passed:
                            subtask.passed = False
                            subtask.failure_status = outcome.status
                            subtask.failure_details = outcome.details
                    continue

                for subtask_id in testcase_subtasks:
                    checker_outcome = run_checker(
                        prepared.problem,
                        testcase,
                        box.root_dir / "box" / "output.txt",
                        subtask_id=subtask_id,
                    )
                    if checker_outcome.status == "AC":
                        continue
                    subtask = subtask_by_id[subtask_id]
                    if subtask.passed:
                        subtask.passed = False
                        subtask.failure_status = checker_outcome.status
                        subtask.failure_details = checker_outcome.details

            if prepared.problem.use_subtask:
                finalize_subtask_outcome(
                    submission_id,
                    subtasks,
                    max_execution_time_ms,
                    max_memory_usage_kb,
                )
                return

            finalize_success(submission_id, len(prepared.testcases), max_execution_time_ms, max_memory_usage_kb)
    except IsolateUnavailableError as exc:
        update_submission_status(submission_id, "RE", str(exc))
    except RuntimeError as exc:
        update_submission_status(submission_id, "RE", str(exc))
