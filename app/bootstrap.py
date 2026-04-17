import shutil
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import Base, engine
from app.models import Problem, Testcase


def init_storage() -> None:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    (settings.data_dir / "problems").mkdir(parents=True, exist_ok=True)
    (settings.data_dir / "submissions").mkdir(parents=True, exist_ok=True)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


def seed_example_problem(db: Session) -> None:
    existing = db.scalar(select(Problem).where(Problem.slug == "a-plus-b"))
    if existing:
        return

    source_dir = Path(__file__).resolve().parent.parent / "problems" / "example_a_plus_b" / "tests"
    target_dir = settings.data_dir / "problems" / "a-plus-b" / "tests"
    target_dir.mkdir(parents=True, exist_ok=True)

    problem = Problem(title="A + B", slug="a-plus-b", time_limit_ms=1000)
    db.add(problem)
    db.flush()

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
