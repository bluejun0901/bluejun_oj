from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class ProblemCoreMixin:
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    time_limit_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=1000)
    memory_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=256)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    input_spec: Mapped[str] = mapped_column(Text, nullable=False, default="")
    output_spec: Mapped[str] = mapped_column(Text, nullable=False, default="")
    examples: Mapped[list[dict[str, str]]] = mapped_column(JSON, nullable=False, default=list)
    use_subtask: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    subtask_info: Mapped[dict[str, dict[str, object]]] = mapped_column(JSON, nullable=False, default=dict)
    checker_source_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)


class TestcaseCoreMixin:
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    input_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    output_path: Mapped[str] = mapped_column(String(1024), nullable=False)


class Problem(Base, ProblemCoreMixin):
    __tablename__ = "problems"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    author_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True, nullable=True)

    testcases: Mapped[list["Testcase"]] = relationship(
        back_populates="problem",
        cascade="all, delete-orphan",
        order_by="Testcase.order_index",
    )
    drafts: Mapped[list["ProblemDraft"]] = relationship(back_populates="source_problem")
    submissions: Mapped[list["Submission"]] = relationship(back_populates="problem")
    author: Mapped["User | None"] = relationship(back_populates="problems")


class ProblemDraft(Base, ProblemCoreMixin):
    __tablename__ = "problem_drafts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    source_problem_id: Mapped[int | None] = mapped_column(ForeignKey("problems.id"), index=True, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.now(timezone.utc),
        onupdate=datetime.now(timezone.utc),
        nullable=False,
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    author: Mapped["User"] = relationship(back_populates="problem_drafts")
    source_problem: Mapped["Problem | None"] = relationship(back_populates="drafts")
    testcases: Mapped[list["DraftTestcase"]] = relationship(
        back_populates="draft",
        cascade="all, delete-orphan",
        order_by="DraftTestcase.order_index",
    )


class Testcase(Base, TestcaseCoreMixin):
    __tablename__ = "testcases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    problem_id: Mapped[int] = mapped_column(ForeignKey("problems.id"), index=True)

    problem: Mapped["Problem"] = relationship(back_populates="testcases")


class DraftTestcase(Base, TestcaseCoreMixin):
    __tablename__ = "draft_testcases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    draft_id: Mapped[int] = mapped_column(ForeignKey("problem_drafts.id"), index=True)

    draft: Mapped["ProblemDraft"] = relationship(back_populates="testcases")


class Submission(Base):
    __tablename__ = "submissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    problem_id: Mapped[int] = mapped_column(ForeignKey("problems.id"), index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True, nullable=True)
    language: Mapped[str] = mapped_column(String(32), nullable=False)
    source_code: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="QUEUED")
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    execution_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    memory_usage_kb: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.now(timezone.utc),
        onupdate=datetime.now(timezone.utc),
        nullable=False,
    )

    problem: Mapped["Problem"] = relationship(back_populates="submissions")
    user: Mapped["User | None"] = relationship(back_populates="submissions")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[str] = mapped_column(String(16), nullable=False, default="user")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.now(timezone.utc),
        onupdate=datetime.now(timezone.utc),
        nullable=False,
    )

    problems: Mapped[list["Problem"]] = relationship(back_populates="author")
    problem_drafts: Mapped[list["ProblemDraft"]] = relationship(back_populates="author")
    submissions: Mapped[list["Submission"]] = relationship(back_populates="user")
    sessions: Mapped[list["UserSession"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )


class UserSession(Base):
    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    session_token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    csrf_token: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.now(timezone.utc), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ip: Mapped[str | None] = mapped_column(String(128), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)

    user: Mapped["User"] = relationship(back_populates="sessions")
