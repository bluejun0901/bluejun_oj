from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class LanguageSpec:
    key: str
    display_name: str
    source_filename: str
    compile_command: tuple[str, ...] | None
    run_command: tuple[str, ...]
    default_source: str
    aliases: tuple[str, ...] = ()
    compile_timeout_seconds: int = 15
    run_process_limit: int = 8
    compile_process_limit: int = 32
    extra_compile_files: tuple[str, ...] = ()
    source_files: tuple[str, ...] = field(default_factory=tuple)

    def resolve_source_files(self) -> tuple[str, ...]:
        if self.source_files:
            return self.source_files
        return (self.source_filename, *self.extra_compile_files)

    def render_compile_command(self, work_dir: Path) -> list[str] | None:
        if self.compile_command is None:
            return None
        return [part.format(work_dir=work_dir, source=self.source_filename) for part in self.compile_command]

    def render_run_command(self, work_dir: Path) -> list[str]:
        return [part.format(work_dir=work_dir, source=self.source_filename) for part in self.run_command]
