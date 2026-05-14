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
    compile_checker_from_root,
    problem_data_dir,
    reset_tests_dir,
    write_checker_source,
)


def init_storage() -> None:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    (settings.data_dir / "drafts").mkdir(parents=True, exist_ok=True)
    (settings.data_dir / "problems").mkdir(parents=True, exist_ok=True)
    (settings.data_dir / "submissions").mkdir(parents=True, exist_ok=True)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


def seed_admin_user(db: Session) -> None:
    if not settings.admin_bootstrap_username or not settings.admin_bootstrap_password:
        return

    admin = db.scalar(select(User).where(User.username == settings.admin_bootstrap_username))
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
        return

    source_root = Path(__file__).resolve().parent.parent / "problems" / "example_a_plus_b"
    source_tests_dir = source_root / "tests"
    problem = Problem(
        author_id=db.scalar(select(User.id).where(User.role == "admin").order_by(User.id.asc())),
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
    )
    db.add(problem)
    db.flush()

    target_tests_dir = reset_tests_dir(problem_data_dir(problem.id))
    for index, input_file in enumerate(sorted(source_tests_dir.glob("*.in")), start=1):
        output_file = input_file.with_suffix(".out")
        target_input = target_tests_dir / f"{index}.in"
        target_output = target_tests_dir / f"{index}.out"
        shutil.copyfile(input_file, target_input)
        shutil.copyfile(output_file, target_output)
        db.add(
            Testcase(
                problem_id=problem.id,
                order_index=index,
                name=input_file.stem,
                input_path=str(target_input),
                output_path=str(target_output),
            )
        )

    checker_path = source_root / "checker.cpp"
    if checker_path.is_file():
        problem.checker_source_path = write_checker_source(
            problem_data_dir(problem.id),
            checker_path.read_text(encoding="utf-8"),
        )

    db.commit()
    try:
        compile_checker_from_root(problem_data_dir(problem.id))
    except CheckerCompileError as exc:
        raise RuntimeError(str(exc)) from exc
