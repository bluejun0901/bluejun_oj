import shutil
from pathlib import Path

from sqlalchemy import inspect, select, text
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
    migrate_existing_db()


def migrate_existing_db() -> None:
    inspector = inspect(engine)
    with engine.begin() as connection:
        if "problems" in inspector.get_table_names():
            columns = {column["name"] for column in inspector.get_columns("problems")}
            if "description" not in columns:
                connection.execute(
                    text("ALTER TABLE problems ADD COLUMN description TEXT NOT NULL DEFAULT ''")
                )
            if "input_spec" not in columns:
                connection.execute(
                    text("ALTER TABLE problems ADD COLUMN input_spec TEXT NOT NULL DEFAULT ''")
                )
            if "output_spec" not in columns:
                connection.execute(
                    text("ALTER TABLE problems ADD COLUMN output_spec TEXT NOT NULL DEFAULT ''")
                )
            if "example_input" not in columns:
                connection.execute(
                    text("ALTER TABLE problems ADD COLUMN example_input TEXT NOT NULL DEFAULT ''")
                )
            if "example_output" not in columns:
                connection.execute(
                    text("ALTER TABLE problems ADD COLUMN example_output TEXT NOT NULL DEFAULT ''")
                )

        if "submissions" in inspector.get_table_names():
            columns = {column["name"] for column in inspector.get_columns("submissions")}
            if "execution_time_ms" not in columns:
                connection.execute(
                    text("ALTER TABLE submissions ADD COLUMN execution_time_ms INTEGER")
                )


def seed_example_problem(db: Session) -> None:
    existing = db.scalar(select(Problem).where(Problem.slug == "a-plus-b"))
    if existing:
        existing.description = (
            existing.description
            or "Read two integers and print their sum."
        )
        existing.input_spec = (
            existing.input_spec
            or "A single line containing two integers `a` and `b`."
        )
        existing.output_spec = (
            existing.output_spec
            or "Print one integer: the value of `a + b` followed by a newline."
        )
        existing.example_input = existing.example_input or "1 2\n"
        existing.example_output = existing.example_output or "3\n"
        db.commit()
        return

    source_dir = Path(__file__).resolve().parent.parent / "problems" / "example_a_plus_b" / "tests"
    target_dir = settings.data_dir / "problems" / "a-plus-b" / "tests"
    target_dir.mkdir(parents=True, exist_ok=True)

    problem = Problem(
        title="A + B",
        slug="a-plus-b",
        time_limit_ms=1000,
        description="Read two integers and print their sum.",
        input_spec="A single line containing two integers `a` and `b`.",
        output_spec="Print one integer: the value of `a + b` followed by a newline.",
        example_input="1 2\n",
        example_output="3\n",
    )
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
