import math
import resource
import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.config import settings
from app.db import SessionLocal
from app.models import Problem, Submission

def update_submission_status(submission_id: int, status: str, details: str | None = None) -> None:
    with SessionLocal() as db:
        submission = db.get(Submission, submission_id)
        if not submission:
            return
        submission.status = status
        submission.details = details
        db.commit()


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

    update_submission_status(submission_id, "JUDGING", "Compilation started")

    with tempfile.TemporaryDirectory(dir=settings.data_dir / "submissions") as tmp_dir_name:
        tmp_dir = Path(tmp_dir_name)
        source_path = tmp_dir / "main.cpp"
        binary_path = tmp_dir / "main"
        source_path.write_text(submission.source_code, encoding="utf-8")

        try:
            compile_result = run_command(
                [
                    "g++",
                    "-std=c++17",
                    "-O2",
                    "-o",
                    str(binary_path),
                    str(source_path),
                ],
                cwd=tmp_dir,
            )
        except FileNotFoundError:
            update_submission_status(submission_id, "CE", "g++ compiler is not installed in the worker")
            return
        if compile_result.returncode != 0:
            details = compile_result.stderr.decode("utf-8", errors="replace")[:4000]
            update_submission_status(submission_id, "CE", details)
            return

        if not binary_path.exists():
            update_submission_status(submission_id, "CE", "Compiler did not produce an executable")
            return

        for testcase in testcases:
            input_path = Path(testcase.input_path)
            expected_path = Path(testcase.output_path)
            stdout_path = tmp_dir / "stdout.txt"

            try:
                with input_path.open("rb") as stdin_file, stdout_path.open("wb") as stdout_file:
                    result = run_command(
                        [str(binary_path)],
                        cwd=tmp_dir,
                        stdin=stdin_file,
                        stdout=stdout_file,
                        timeout=max(1, math.ceil(problem.time_limit_ms / 1000) + 1),
                        preexec_fn=create_runtime_limits(
                            problem.time_limit_ms,
                            settings.default_memory_limit_mb,
                        ),
                    )
            except subprocess.TimeoutExpired:
                update_submission_status(
                    submission_id,
                    "TLE",
                    f"Time limit exceeded on testcase {testcase.order_index}",
                )
                return
            except FileNotFoundError:
                update_submission_status(submission_id, "RE", "Compiled executable was not found")
                return

            if result.returncode != 0:
                stderr = result.stderr.decode("utf-8", errors="replace")[:4000]
                detail = stderr or f"Runtime error on testcase {testcase.order_index}"
                update_submission_status(submission_id, "RE", detail)
                return

            actual = stdout_path.read_bytes() if stdout_path.exists() else b""
            expected = expected_path.read_bytes()
            if actual != expected:
                update_submission_status(
                    submission_id,
                    "WA",
                    f"Wrong answer on testcase {testcase.order_index}",
                )
                return

        update_submission_status(submission_id, "AC", f"Accepted ({len(testcases)} testcases)")
