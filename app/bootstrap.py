import shutil
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import hash_password
from app.config import settings
from app.db import Base, engine
from app.models import Problem, Testcase, User
from app.problem_assets import (
    CheckerCompileError,
    compile_checker,
    reset_problem_tests_directory,
)


def init_storage() -> None:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    (settings.data_dir / "problems").mkdir(parents=True, exist_ok=True)
    (settings.data_dir / "submissions").mkdir(parents=True, exist_ok=True)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


def seed_admin_user(db: Session) -> None:
    if not settings.admin_bootstrap_username or not settings.admin_bootstrap_password:
        return

    admin = db.scalar(
        select(User).where(User.username == settings.admin_bootstrap_username)
    )
    if admin:
        return

    db.add(
        User(
            username=settings.admin_bootstrap_username,
            password_hash=hash_password(settings.admin_bootstrap_password),
            display_name=settings.admin_bootstrap_username,
            role="admin",
        )
    )
    db.commit()


def seed_example_problem(db: Session) -> None:
    existing = db.scalar(select(Problem).where(Problem.slug == "a-plus-b"))
    if existing:
        if existing.author_id is None:
            existing.author_id = db.scalar(
                select(User.id).where(User.role == "admin").order_by(User.id.asc())
            )
        existing.description = (
            existing.description or "Read two integers and print their sum."
        )
        existing.input_spec = (
            existing.input_spec or "A single line containing two integers `a` and `b`."
        )
        existing.output_spec = (
            existing.output_spec
            or "Print one integer: the value of `a + b` followed by a newline."
        )
        existing.memory_limit = existing.memory_limit or 256
        existing.examples = existing.examples or [
            {"input": "1 2\n", "output": "3\n"},
            {"input": "30 40\n", "output": "70\n"},
        ]
        existing.use_subtask = True
        existing.subtask_info = {
            "1": {
                "desc": "All values fit in 32-bit signed integers: $-2^{31} \\le a, b \\le 2^{31}-1$.",
                "score": 50,
                "cases": [1, 2],
            },
            "2": {
                "desc": "Full range where values fit in 64-bit signed integers: $-2^{63} \\le a, b \\le 2^{63}-1$.",
                "score": 50,
                "cases": [3],
            },
        }
        existing.checker_source_path = (
            existing.checker_source_path or "problems/example_a_plus_b"
        )
        db.commit()
        try:
            compile_checker(existing)
        except CheckerCompileError as exc:
            raise RuntimeError(str(exc)) from exc
        return

    source_dir = (
        Path(__file__).resolve().parent.parent
        / "problems"
        / "example_a_plus_b"
        / "tests"
    )

    problem = Problem(
        author_id=db.scalar(
            select(User.id).where(User.role == "admin").order_by(User.id.asc())
        ),
        title="A + B",
        slug="a-plus-b",
        time_limit_ms=1000,
        memory_limit=256,
        description="Read two integers and print their sum.",
        input_spec="A single line containing two integers `a` and `b`.",
        output_spec="Print one integer: the value of `a + b` followed by a newline.",
        examples=[
            {"input": "1 2\n", "output": "3\n"},
            {"input": "30 40\n", "output": "70\n"},
        ],
        use_subtask=True,
        subtask_info={
            "1": {
                "desc": "All values fit in 32-bit signed integers: $-2^{31} \\le a, b \\le 2^{31}-1$.",
                "score": 50,
                "cases": [1, 2],
            },
            "2": {
                "desc": "Full range where values fit in 64-bit signed integers: $-2^{63} \\le a, b \\le 2^{63}-1$.",
                "score": 50,
                "cases": [3],
            },
        },
        checker_source_path="problems/example_a_plus_b",
    )
    db.add(problem)
    db.flush()

    target_dir = reset_problem_tests_directory(problem.id)

    inputs = sorted(source_dir.glob("*.in"))
    for index, input_file in enumerate(inputs, start=1):
        output_file = input_file.with_suffix(".out")
        target_input = target_dir / input_file.name
        target_output = target_dir / output_file.name
        shutil.copyfile(input_file, target_input)
        shutil.copyfile(output_file, target_output)
        db.add(
            Testcase(
                problem_id=problem.id,
                order_index=index,
                input_path=str(target_input),
                output_path=str(target_output),
            )
        )

    db.commit()
    try:
        compile_checker(problem)
    except CheckerCompileError as exc:
        raise RuntimeError(str(exc)) from exc
