from dataclasses import dataclass
from pathlib import Path
import shutil

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.config import settings
from app.db import SessionLocal
from app.languages import get_language
from app.languages.types import LanguageSpec
from app.models import Problem, Submission, Testcase
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


def update_submission_status(
    submission_id: int,
    status: str,
    details: str | None = None,
    execution_time_ms: int | None = None,
    memory_usage_kb: int | None = None,
) -> None:
    with SessionLocal() as db:
        submission = db.get(Submission, submission_id)
        if not submission:
            return
        submission.status = status
        submission.details = details
        submission.execution_time_ms = execution_time_ms
        submission.memory_usage_kb = memory_usage_kb
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
    print(message)
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
    output_path = Path(testcase.output_path)
    if not input_path.exists():
        raise RuntimeError(f"Missing testcase input file: {input_path}")
    if not output_path.exists():
        raise RuntimeError(f"Missing testcase output file: {output_path}")
    copy_into_box(box, input_path, "input.txt")


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
        memory_limit_mb=settings.default_memory_limit_mb,
        process_limit=language.run_process_limit,
        stdin_name="input.txt",
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

    actual = result.stdout
    expected = Path(testcase.output_path).read_bytes()
    if actual != expected:
        return JudgeOutcome(
            status="WA",
            details=f"Wrong answer on testcase {testcase.order_index}",
            execution_time_ms=execution_time_ms,
            memory_usage_kb=memory_usage_kb,
        )

    return JudgeOutcome(
        status="AC",
        details=f"Accepted testcase {testcase.order_index}",
        execution_time_ms=execution_time_ms,
        memory_usage_kb=memory_usage_kb,
    )


def finalize_success(submission_id: int, testcase_count: int, max_execution_time_ms: int, max_memory_usage_kb: int) -> None:
    update_submission_status(
        submission_id,
        "AC",
        f"Accepted ({testcase_count} testcases)",
        max_execution_time_ms or None,
        max_memory_usage_kb or None,
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
                if outcome.status != "AC":
                    apply_outcome(submission_id, outcome)
                    return

            finalize_success(submission_id, len(prepared.testcases), max_execution_time_ms, max_memory_usage_kb)
    except IsolateUnavailableError as exc:
        update_submission_status(submission_id, "RE", str(exc))
    except RuntimeError as exc:
        update_submission_status(submission_id, "RE", str(exc))
