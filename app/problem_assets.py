from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from app.config import settings
from app.models import Problem


REPO_ROOT = Path(__file__).resolve().parent.parent
CHECKER_BINARY_NAME = "checker"


class CheckerCompileError(RuntimeError):
    pass


def problem_data_dir(problem_id: int) -> Path:
    return settings.data_dir / "problems" / str(problem_id)


def problem_tests_dir(problem_id: int) -> Path:
    return problem_data_dir(problem_id) / "tests"


def checker_binary_path(problem_id: int) -> Path:
    return problem_data_dir(problem_id) / CHECKER_BINARY_NAME


def resolve_checker_source_dir(problem: Problem) -> Path:
    candidates: list[Path] = []
    if problem.checker_source_path:
        configured_path = Path(problem.checker_source_path)
        candidates.append(
            configured_path
            if configured_path.is_absolute()
            else REPO_ROOT / configured_path
        )

    slug_underscored = problem.slug.replace("-", "_")
    candidates.extend(
        [
            REPO_ROOT / "problems" / problem.slug,
            REPO_ROOT / "problems" / slug_underscored,
            REPO_ROOT / "problems" / f"example_{slug_underscored}",
        ]
    )

    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    searched = ", ".join(str(path) for path in candidates)
    raise CheckerCompileError(
        f"Checker source directory not found for problem '{problem.slug}'. Searched: {searched}"
    )


def checker_source_file(problem: Problem) -> Path:
    source_dir = resolve_checker_source_dir(problem)
    checker_path = source_dir / "checker.cpp"
    if not checker_path.is_file():
        raise CheckerCompileError(f"Checker source file not found: {checker_path}")
    return checker_path


def compile_checker(problem: Problem) -> Path:
    source_path = checker_source_file(problem)
    output_path = checker_binary_path(problem.id)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    command = [
        "/usr/bin/g++",
        "-std=c++17",
        "-O2",
        "-pipe",
        "-I",
        str(REPO_ROOT / "source"),
        str(source_path),
        "-o",
        str(output_path),
    ]
    result = subprocess.run(command, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        details = (
            result.stderr or result.stdout
        ).strip() or "unknown checker compilation error"
        raise CheckerCompileError(f"Failed to compile checker: {details}")

    output_path.chmod(0o755)
    return output_path


def reset_problem_tests_directory(problem_id: int) -> Path:
    tests_dir = problem_tests_dir(problem_id)
    if tests_dir.exists():
        shutil.rmtree(tests_dir)
    tests_dir.mkdir(parents=True, exist_ok=True)
    return tests_dir
