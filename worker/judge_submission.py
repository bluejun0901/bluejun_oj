from pathlib import Path

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


def compile_submission(submission_id: int, box, language) -> bool:
    compile_command = language.render_compile_command(box.root_dir)
    if compile_command is None:
        return True

    update_submission_status(submission_id, "JUDGING", "Compilation started")
    result = run_in_box(
        box,
        compile_command,
        time_limit_ms=language.compile_timeout_seconds * 1000,
        wall_time_ms=(language.compile_timeout_seconds + 5) * 1000,
        memory_limit_mb=max(settings.default_memory_limit_mb, 512),
        process_limit=language.compile_process_limit,
        stdout_name="compile.stdout",
        stderr_name="compile.stderr",
    )
    if result.returncode != 0:
        details = summarize_stderr(result) or "Compilation failed"
        update_submission_status(submission_id, "CE", details)
        return False
    return True


def judge_testcase(submission_id: int, box, language, testcase, problem) -> tuple[bool, int, int]:
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

    try:
        with isolate_box() as box:
            write_into_box(box, language.source_filename, submission.source_code)
            if not compile_submission(submission_id, box, language):
                return

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
