from datetime import datetime

from pydantic import BaseModel, Field


class UserSummary(BaseModel):
    id: int
    username: str
    display_name: str | None

    @classmethod
    def from_model(cls, user):
        return cls(
            id=user.id,
            username=user.username,
            display_name=user.display_name,
        )


class AuthUserOut(UserSummary):
    role: str

    @classmethod
    def from_model(cls, user):
        return cls(
            id=user.id,
            username=user.username,
            display_name=user.display_name,
            role=user.role,
        )


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=32, pattern=r"^[a-zA-Z0-9_][a-zA-Z0-9_-]*$")
    password: str = Field(min_length=8, max_length=128)
    display_name: str | None = Field(default=None, max_length=100)
    email: str | None = Field(default=None, max_length=255)


class LoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=8, max_length=128)


class ExampleCreate(BaseModel):
    input: str
    output: str


class TestcaseCreate(BaseModel):
    input: str
    output: str


class SubtaskInfoEntry(BaseModel):
    desc: str = ""
    score: int = Field(ge=0)
    cases: list[int] = Field(default_factory=list)


class ProblemCreate(BaseModel):
    title: str
    slug: str = Field(pattern=r"^[a-zA-Z0-9_-]+$")
    time_limit_ms: int = Field(gt=0, le=10000)
    memory_limit: int = Field(gt=0, le=4096)
    description: str = ""
    input_spec: str = ""
    output_spec: str = ""
    examples: list[ExampleCreate] = Field(default_factory=list)
    use_subtask: bool = False
    subtask_info: dict[str, SubtaskInfoEntry] = Field(default_factory=dict)
    checker_source_path: str | None = None
    testcases: list[TestcaseCreate]


class ProblemOut(BaseModel):
    id: int
    author: UserSummary | None
    title: str
    slug: str
    time_limit_ms: int
    memory_limit: int
    description: str
    input_spec: str
    output_spec: str
    examples: list[ExampleCreate]
    use_subtask: bool
    subtask_info: dict[str, SubtaskInfoEntry]
    testcase_count: int

    @classmethod
    def from_model(cls, problem):
        return cls(
            id=problem.id,
            author=UserSummary.from_model(problem.author) if problem.author else None,
            title=problem.title,
            slug=problem.slug,
            time_limit_ms=problem.time_limit_ms,
            memory_limit=problem.memory_limit,
            description=problem.description,
            input_spec=problem.input_spec,
            output_spec=problem.output_spec,
            examples=problem.examples or [],
            use_subtask=problem.use_subtask,
            subtask_info=problem.subtask_info or {},
            testcase_count=len(problem.testcases),
        )


class LanguageOut(BaseModel):
    key: str
    display_name: str
    default_source: str

    @classmethod
    def from_spec(cls, spec):
        return cls(
            key=spec.key,
            display_name=spec.display_name,
            default_source=spec.default_source,
        )


class SubmissionCreate(BaseModel):
    problem_id: int
    language: str
    source_code: str


class SubmissionOut(BaseModel):
    id: int
    problem_id: int
    user: UserSummary | None
    is_mine: bool = False
    language: str
    status: str
    details: str | None
    execution_time_ms: int | None
    memory_usage_kb: int | None
    score: int | None
    max_score: int | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_model(cls, submission, *, viewer_id: int | None = None):
        return cls(
            id=submission.id,
            problem_id=submission.problem_id,
            user=UserSummary.from_model(submission.user) if submission.user else None,
            is_mine=viewer_id is not None and submission.user_id == viewer_id,
            language=submission.language,
            status=submission.status,
            details=submission.details,
            execution_time_ms=submission.execution_time_ms,
            memory_usage_kb=submission.memory_usage_kb,
            score=submission.score,
            max_score=submission.max_score,
            created_at=submission.created_at,
            updated_at=submission.updated_at,
        )
