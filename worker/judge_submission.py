from pathlib import Path
import subprocess

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.config import settings
from app.db import SessionLocal
from app.languages import get_language
from app.models import Problem, Submission
from worker.isolate_runner import (
    IsolateResult,
    IsolateUnavailableError,
    copy_into_box,
    isolate_box,
    run_in_box,
    write_into_box,
)


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
    return result.meta.get("cg-oom-killed") == "1" or "memory" in message


def _run_command(args: list[str], cwd: Path | str) -> subprocess.CompletedProcess[bytes]:
    try:
        return subprocess.run(args, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=cwd)
    except FileNotFoundError as exc:
        raise RuntimeError(f"Required command not found: {args[0]}") from exc


def compile_submission(submission_id: int, source_path: Path, language) -> bool:
    compile_command = language.render_compile_command(source_path.parent)
    if compile_command is None:
        return True
    
    args = [
        "timeout",
        f"{language.compile_timeout_seconds}s",
    ] + compile_command
    
    result = _run_command(args, cwd=source_path.parent)

    if result.returncode != 0:
        details = result.stderr.decode("utf-8", errors="replace").strip()[:4000] or "Compilation failed"
        update_submission_status(submission_id, "CE", details)
        return False
    return True


def judge_testcase(submission_id: int, box, language, testcase, problem) -> tuple[bool, int, int]:
    print(testcase.input_path, testcase.output_path)
    copy_into_box(box, Path(testcase.input_path), "input.txt")
    result = run_in_box(
        box,
        language.render_run_command(box.root_dir),
        time_limit_ms=problem.time_limit_ms,
        wall_time_ms=problem.time_limit_ms + 1000,
        memory_limit_mb=settings.default_memory_limit_mb,
        process_limit=language.run_process_limit,
        stdin_name="input.txt",
    )
    execution_time_ms, memory_usage_kb = execution_metrics(result)
    execution_time_ms = execution_time_ms or 0
    memory_usage_kb = memory_usage_kb or 0

    if result.status == "TO":
        update_submission_status(
            submission_id,
            "TLE",
            f"Time limit exceeded on testcase {testcase.order_index}",
            execution_time_ms,
            memory_usage_kb,
        )
        return False, execution_time_ms, memory_usage_kb

    if is_memory_limit_exceeded(result):
        update_submission_status(
            submission_id,
            "MLE",
            f"Memory limit exceeded on testcase {testcase.order_index}",
            execution_time_ms or None,
            memory_usage_kb or None,
        )
        return False, execution_time_ms, memory_usage_kb

    if result.returncode != 0 or result.status in {"RE", "SG", "XX"}:
        detail = summarize_stderr(result) or f"Runtime error on testcase {testcase.order_index}"
        update_submission_status(
            submission_id,
            "RE",
            detail,
            execution_time_ms or None,
            memory_usage_kb or None,
        )
        return False, execution_time_ms, memory_usage_kb

    actual = result.stdout
    expected = Path(testcase.output_path).read_bytes()
    if actual != expected:
        update_submission_status(
            submission_id,
            "WA",
            f"Wrong answer on testcase {testcase.order_index}",
            execution_time_ms or None,
            memory_usage_kb or None,
        )
        return False, execution_time_ms, memory_usage_kb

    return True, execution_time_ms, memory_usage_kb

def _write_into_folder(target_path: Path | str, content: str) -> Path:
    target_path = Path(target_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(content, encoding="utf-8")
    return target_path

def judge_submission(submission_id: int) -> None:
    with SessionLocal() as db:
        submission = db.scalar(
            select(Submission)
            .where(Submission.id == submission_id)
            .options(selectinload(Submission.problem).selectinload(Problem.testcases))
        )
        if not submission:
            return
        problem = submission.problem
        testcases = sorted(problem.testcases, key=lambda tc: tc.order_index)

    update_submission_status(submission_id, "JUDGING", "Preparing execution")
    try:
        language = get_language(submission.language)
    except ValueError as exc:
        update_submission_status(submission_id, "CE", str(exc))
        return

    work_directory = Path(settings.data_dir) / "submissions" / f"{submission_id}"

    try:
        source_path = _write_into_folder(work_directory / language.source_filename, submission.source_code)
        if not compile_submission(submission_id, source_path, language):
            return

        with isolate_box() as box:
            for p in work_directory.iterdir():
                copy_into_box(box, p, p.name)

            max_execution_time_ms = 0
            max_memory_usage_kb = 0

            for testcase in testcases:
                accepted, execution_time_ms, memory_usage_kb = judge_testcase(
                    submission_id,
                    box,
                    language,
                    testcase,
                    problem,
                )
                max_execution_time_ms = max(max_execution_time_ms, execution_time_ms)
                max_memory_usage_kb = max(max_memory_usage_kb, memory_usage_kb)
                if not accepted:
                    return

            update_submission_status(
                submission_id,
                "AC",
                f"Accepted ({len(testcases)} testcases)",
                max_execution_time_ms or None,
                max_memory_usage_kb or None,
            )
    except IsolateUnavailableError as exc:
        update_submission_status(submission_id, "RE", str(exc))
    except RuntimeError as exc:
        update_submission_status(submission_id, "RE", str(exc))
