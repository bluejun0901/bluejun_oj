import math
import resource
import subprocess
import tempfile
import time
from collections.abc import Callable
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.config import settings
from app.db import SessionLocal
from app.models import Problem, Submission

def update_submission_status(
    submission_id: int,
    status: str,
    details: str | None = None,
    execution_time_ms: int | None = None,
) -> None:
    with SessionLocal() as db:
        submission = db.get(Submission, submission_id)
        if not submission:
            return
        submission.status = status
        submission.details = details
        submission.execution_time_ms = execution_time_ms
        db.commit()


def get_language_config(language: str, work_dir: Path) -> tuple[Path, list[str] | None, list[str]]:
    if language == "python":
        source_path = work_dir / "main.py"
        return source_path, None, ["python3", str(source_path)]

    source_path = work_dir / "main.cpp"
    binary_path = work_dir / "main"
    return (
        source_path,
        ["g++", "-std=c++17", "-O2", "-o", str(binary_path), str(source_path)],
        [str(binary_path)],
    )


def run_command(
    command: list[str],
    timeout: int | None = None,
    cwd: Path | None = None,
    stdin=None,
    stdout=None,
    preexec_fn: Callable[[], None] | None = None,
) -> subprocess.CompletedProcess:
    return subprocess.run(
        command,
        cwd=cwd,
        stdin=stdin,
        stdout=subprocess.PIPE if stdout is None else stdout,
        stderr=subprocess.PIPE,
        text=False,
        timeout=timeout,
        check=False,
        preexec_fn=preexec_fn,
    )


def create_runtime_limits(time_limit_ms: int, memory_limit_mb: int) -> Callable[[], None]:
    cpu_seconds = max(1, math.ceil(time_limit_ms / 1000))
    memory_bytes = memory_limit_mb * 1024 * 1024

    def apply_limits() -> None:
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds + 1))
        resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))

    return apply_limits


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

    with tempfile.TemporaryDirectory(dir=settings.data_dir / "submissions") as tmp_dir_name:
        tmp_dir = Path(tmp_dir_name)
        source_path, compile_command, run_command_args = get_language_config(submission.language, tmp_dir)
        source_path.write_text(submission.source_code, encoding="utf-8")

        if compile_command:
            update_submission_status(submission_id, "JUDGING", "Compilation started")
            try:
                compile_result = run_command(
                    compile_command,
                    cwd=tmp_dir,
                )
            except FileNotFoundError:
                update_submission_status(
                    submission_id,
                    "CE",
                    "g++ compiler is not installed in the worker",
                )
                return
            if compile_result.returncode != 0:
                details = compile_result.stderr.decode("utf-8", errors="replace")[:4000]
                update_submission_status(submission_id, "CE", details)
                return

            if not Path(run_command_args[0]).exists():
                update_submission_status(submission_id, "CE", "Compiler did not produce an executable")
                return

        max_execution_time_ms = 0

        for testcase in testcases:
            input_path = Path(testcase.input_path)
            expected_path = Path(testcase.output_path)
            stdout_path = tmp_dir / "stdout.txt"

            try:
                with input_path.open("rb") as stdin_file, stdout_path.open("wb") as stdout_file:
                    started_at = time.perf_counter()
                    result = run_command(
                        run_command_args,
                        cwd=tmp_dir,
                        stdin=stdin_file,
                        stdout=stdout_file,
                        timeout=max(1, math.ceil(problem.time_limit_ms / 1000) + 1),
                        preexec_fn=create_runtime_limits(
                            problem.time_limit_ms,
                            settings.default_memory_limit_mb,
                        ),
                    )
                    elapsed_ms = max(1, int((time.perf_counter() - started_at) * 1000))
                    max_execution_time_ms = max(max_execution_time_ms, elapsed_ms)
            except subprocess.TimeoutExpired:
                update_submission_status(
                    submission_id,
                    "TLE",
                    f"Time limit exceeded on testcase {testcase.order_index}",
                    problem.time_limit_ms,
                )
                return
            except FileNotFoundError:
                detail = (
                    "python3 runtime is not installed in the worker"
                    if submission.language == "python"
                    else "Compiled executable was not found"
                )
                update_submission_status(submission_id, "RE", detail, max_execution_time_ms or None)
                return

            if result.returncode != 0:
                stderr = result.stderr.decode("utf-8", errors="replace")[:4000]
                detail = stderr or f"Runtime error on testcase {testcase.order_index}"
                update_submission_status(submission_id, "RE", detail, max_execution_time_ms or None)
                return

            actual = stdout_path.read_bytes() if stdout_path.exists() else b""
            expected = expected_path.read_bytes()
            if actual != expected:
                update_submission_status(
                    submission_id,
                    "WA",
                    f"Wrong answer on testcase {testcase.order_index}",
                    max_execution_time_ms or None,
                )
                return

        update_submission_status(
            submission_id,
            "AC",
            f"Accepted ({len(testcases)} testcases)",
            max_execution_time_ms or None,
        )
