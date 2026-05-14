from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from app.config import settings

REPO_ROOT = Path(__file__).resolve().parent.parent
CHECKER_BINARY_NAME = "checker"
CHECKER_SOURCE_NAME = "checker.cpp"


class CheckerCompileError(RuntimeError):
    pass


def problem_data_dir(problem_id: int) -> Path:
    return settings.data_dir / "problems" / str(problem_id)


def draft_data_dir(draft_id: int) -> Path:
    return settings.data_dir / "drafts" / str(draft_id)


def tests_dir(root_dir: Path) -> Path:
    return root_dir / "tests"


def checker_binary_path(root_dir: Path) -> Path:
    return root_dir / CHECKER_BINARY_NAME


def checker_source_path(root_dir: Path) -> Path:
    return root_dir / CHECKER_SOURCE_NAME


def ensure_data_dir(root_dir: Path) -> None:
    root_dir.mkdir(parents=True, exist_ok=True)
    tests_dir(root_dir).mkdir(parents=True, exist_ok=True)


def reset_tests_dir(root_dir: Path) -> Path:
    target = tests_dir(root_dir)
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True, exist_ok=True)
    return target


def write_checker_source(root_dir: Path, source_code: str) -> str:
    ensure_data_dir(root_dir)
    target = checker_source_path(root_dir)
    target.write_text(source_code, encoding="utf-8")
    return str(target)


def read_text_asset(path: str | None) -> str:
    if not path:
        return ""
    target = Path(path)
    if not target.is_file():
        return ""
    return target.read_text(encoding="utf-8")


def write_testcase_files(root_dir: Path, cases: list[dict[str, str]]) -> list[dict[str, str]]:
    target_dir = reset_tests_dir(root_dir)
    written: list[dict[str, str]] = []
    for index, testcase in enumerate(cases, start=1):
        stem = testcase.get("name") or f"case-{index}"
        input_path = target_dir / f"{index}.in"
        output_path = target_dir / f"{index}.out"
        input_path.write_text(testcase["input"], encoding="utf-8")
        output_path.write_text(testcase["output"], encoding="utf-8")
        written.append(
            {
                "order_index": index,
                "name": stem,
                "input_path": str(input_path),
                "output_path": str(output_path),
            }
        )
    return written


def read_testcase_text(input_path: str, output_path: str) -> dict[str, str]:
    return {
        "input": Path(input_path).read_text(encoding="utf-8"),
        "output": Path(output_path).read_text(encoding="utf-8"),
    }


def compile_checker_source(source_path: Path, output_path: Path) -> Path:
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
        details = (result.stderr or result.stdout).strip() or "unknown checker compilation error"
        raise CheckerCompileError(f"Failed to compile checker: {details}")
    output_path.chmod(0o755)
    return output_path


def compile_checker_from_root(root_dir: Path) -> Path:
    source = checker_source_path(root_dir)
    if not source.is_file():
        raise CheckerCompileError(f"Checker source file not found: {source}")
    return compile_checker_source(source, checker_binary_path(root_dir))
