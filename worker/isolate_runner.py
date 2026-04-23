from __future__ import annotations

import itertools
import shutil
import subprocess
from contextlib import contextmanager
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from collections.abc import Iterator

from app.config import settings


class IsolateUnavailableError(RuntimeError):
    pass


@dataclass
class IsolateResult:
    returncode: int
    stdout: bytes
    stderr: bytes
    sandbox_stderr: bytes
    meta: dict[str, str]

    @property
    def status(self) -> str | None:
        return self.meta.get("status")

    @property
    def time_ms(self) -> int | None:
        value = self.meta.get("time")
        if value is None:
            return None
        return max(1, int(float(value) * 1000))

    @property
    def wall_time_ms(self) -> int | None:
        value = self.meta.get("time-wall")
        if value is None:
            return None
        return max(1, int(float(value) * 1000))

    @property
    def memory_kb(self) -> int | None:
        value = self.meta.get("cg-mem")
        if value is None:
            return None
        return int(value)


@dataclass
class IsolateBox:
    box_id: int
    root_dir: Path
    use_cgroup: bool


_BOX_IDS = itertools.cycle(range(10, 100))
_VALID_CGROUP_MODES = {"auto", "always", "never"}


def _parse_meta(meta_path: Path) -> dict[str, str]:
    if not meta_path.exists():
        return {}

    meta: dict[str, str] = {}
    for line in meta_path.read_text(encoding="utf-8", errors="replace").splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        meta[key.strip()] = value.strip()
    return meta


def _run_isolate_command(args: list[str]) -> subprocess.CompletedProcess[bytes]:
    try:
        return subprocess.run(args, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except FileNotFoundError as exc:
        raise IsolateUnavailableError("isolate is not installed in the worker environment") from exc


def _is_cgroup_init_error(stderr: bytes) -> bool:
    detail = stderr.decode("utf-8", errors="replace").lower()
    return "cgroup" in detail


def _should_use_cgroup() -> bool:
    mode = settings.isolate_cgroup_mode
    if mode not in _VALID_CGROUP_MODES:
        mode = "auto"
    if mode == "always":
        return True
    if mode == "never":
        return False
    return _detect_cgroup_support()


@lru_cache(maxsize=1)
def _detect_cgroup_support() -> bool:
    probe_box_id = 999
    init_result = _run_isolate_command(["isolate", f"--box-id={probe_box_id}", "--cg", "--init"])
    if init_result.returncode == 0:
        _run_isolate_command(["isolate", f"--box-id={probe_box_id}", "--cg", "--cleanup"])
        return True
    if _is_cgroup_init_error(init_result.stderr):
        return False
    detail = init_result.stderr.decode("utf-8", errors="replace").strip()
    raise RuntimeError(f"failed to initialize isolate sandbox: {detail or 'unknown error'}")


@contextmanager
def isolate_box() -> Iterator[IsolateBox]:
    box_id = next(_BOX_IDS)
    use_cgroup = _should_use_cgroup()
    init_args = ["isolate", f"--box-id={box_id}"]
    if use_cgroup:
        init_args.append("--cg")
    init_args.append("--init")
    init_result = _run_isolate_command(init_args)
    if init_result.returncode != 0:
        detail = init_result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"failed to initialize isolate sandbox: {detail or 'unknown error'}")

    root_dir = Path(init_result.stdout.decode("utf-8", errors="replace").strip())
    if not root_dir.exists():
        raise RuntimeError("isolate returned an invalid sandbox path")

    try:
        yield IsolateBox(box_id=box_id, root_dir=root_dir, use_cgroup=use_cgroup)
    finally:
        cleanup_args = ["isolate", f"--box-id={box_id}"]
        if use_cgroup:
            cleanup_args.append("--cg")
        cleanup_args.append("--cleanup")
        _run_isolate_command(cleanup_args)


def copy_into_box(box: IsolateBox, source: Path, target_name: str) -> None:
    target_path = box.root_dir / "box" / target_name
    target_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target_path)


def write_into_box(box: IsolateBox, target_name: str, content: str) -> Path:
    target_path = box.root_dir / "box" / target_name
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(content, encoding="utf-8")
    return target_path


def run_in_box(
    box: IsolateBox,
    command: list[str],
    *,
    time_limit_ms: int,
    wall_time_ms: int,
    memory_limit_mb: int,
    process_limit: int,
    stdin_name: str | None = None,
    stdout_name: str = "stdout.txt",
    stderr_name: str = "stderr.txt",
) -> IsolateResult:
    meta_path = box.root_dir / "meta.txt"
    stdout_path = box.root_dir / "box" / stdout_name
    stderr_path = box.root_dir / "box" / stderr_name

    for path in (meta_path, stdout_path, stderr_path):
        if path.exists():
            path.unlink()

    args = [
        "isolate",
        f"--box-id={box.box_id}",
        f"--meta={meta_path}",
        f"--time={max(1, time_limit_ms) / 1000:.3f}",
        f"--wall-time={max(1, wall_time_ms) / 1000:.3f}",
        f"--processes={process_limit}",
        f"--stdout={stdout_name}",
        f"--stderr={stderr_name}",
    ]
    if box.use_cgroup:
        args.extend(["--cg", f"--cg-mem={memory_limit_mb * 1024}"])
    else:
        args.append(f"--mem={memory_limit_mb * 1024}")
    if stdin_name is not None:
        args.append(f"--stdin={stdin_name}")
    args.extend(["--run", "--", *command])

    result = _run_isolate_command(args)
    meta = _parse_meta(meta_path)
    return IsolateResult(
        returncode=result.returncode,
        stdout=stdout_path.read_bytes() if stdout_path.exists() else b"",
        stderr=stderr_path.read_bytes() if stderr_path.exists() else b"",
        sandbox_stderr=result.stderr,
        meta=meta,
    )
