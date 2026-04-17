from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Problem(Base):
    __tablename__ = "problems"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    time_limit_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=1000)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    input_spec: Mapped[str] = mapped_column(Text, nullable=False, default="")
    output_spec: Mapped[str] = mapped_column(Text, nullable=False, default="")
    example_input: Mapped[str] = mapped_column(Text, nullable=False, default="")
    example_output: Mapped[str] = mapped_column(Text, nullable=False, default="")

    testcases: Mapped[list["Testcase"]] = relationship(
        back_populates="problem",
        cascade="all, delete-orphan",
        order_by="Testcase.order_index",
    )
    submissions: Mapped[list["Submission"]] = relationship(back_populates="problem")


class Testcase(Base):
    __tablename__ = "testcases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    problem_id: Mapped[int] = mapped_column(ForeignKey("problems.id"), index=True)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    input_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    output_path: Mapped[str] = mapped_column(String(1024), nullable=False)

    problem: Mapped["Problem"] = relationship(back_populates="testcases")


class Submission(Base):
    __tablename__ = "submissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    problem_id: Mapped[int] = mapped_column(ForeignKey("problems.id"), index=True)
    language: Mapped[str] = mapped_column(String(32), nullable=False)
    source_code: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="QUEUED")
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    execution_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    problem: Mapped["Problem"] = relationship(back_populates="submissions")
