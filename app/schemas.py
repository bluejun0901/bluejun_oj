from datetime import datetime

from pydantic import BaseModel, Field


class TestcaseCreate(BaseModel):
    input: str
    output: str


class ProblemCreate(BaseModel):
    title: str
    slug: str = Field(pattern=r"^[a-zA-Z0-9_-]+$")
    time_limit_ms: int = Field(gt=0, le=10000)
    description: str = ""
    input_spec: str = ""
    output_spec: str = ""
    example_input: str = ""
    example_output: str = ""
    testcases: list[TestcaseCreate]


class ProblemOut(BaseModel):
    id: int
    title: str
    slug: str
    time_limit_ms: int
    description: str
    input_spec: str
    output_spec: str
    example_input: str
    example_output: str
    testcase_count: int

    @classmethod
    def from_model(cls, problem):
        return cls(
            id=problem.id,
            title=problem.title,
            slug=problem.slug,
            time_limit_ms=problem.time_limit_ms,
            description=problem.description,
            input_spec=problem.input_spec,
            output_spec=problem.output_spec,
            example_input=problem.example_input,
            example_output=problem.example_output,
            testcase_count=len(problem.testcases),
        )


class SubmissionCreate(BaseModel):
    problem_id: int
    language: str
    source_code: str


class SubmissionOut(BaseModel):
    id: int
    problem_id: int
    language: str
    status: str
    details: str | None
    execution_time_ms: int | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_model(cls, submission):
        return cls(
            id=submission.id,
            problem_id=submission.problem_id,
            language=submission.language,
            status=submission.status,
            details=submission.details,
            execution_time_ms=submission.execution_time_ms,
            created_at=submission.created_at,
            updated_at=submission.updated_at,
        )
