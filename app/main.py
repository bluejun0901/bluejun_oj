from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.bootstrap import init_db, init_storage, seed_example_problem
from app.config import settings
from app.db import SessionLocal, get_db
from app.languages import get_language, list_languages
from app.models import Problem, Submission, Testcase
from app.queue import get_queue
from app.schemas import LanguageOut, ProblemCreate, ProblemOut, SubmissionCreate, SubmissionOut

app = FastAPI(title="Minimal OJ")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    init_storage()
    init_db()
    with SessionLocal() as db:
        seed_example_problem(db)


@app.get("/health")
def health():
    return {"status": "ok"}


def normalize_language(language: str) -> str:
    try:
        return get_language(language).key
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/languages", response_model=list[LanguageOut])
def get_languages():
    return [LanguageOut.from_spec(spec) for spec in list_languages()]


@app.get("/problems", response_model=list[ProblemOut])
def list_problems(db: Session = Depends(get_db)):
    problems = db.scalars(select(Problem).options(selectinload(Problem.testcases))).all()
    return [ProblemOut.from_model(problem) for problem in problems]


@app.get("/problems/{problem_id}", response_model=ProblemOut)
def get_problem(problem_id: int, db: Session = Depends(get_db)):
    problem = db.scalar(
        select(Problem).where(Problem.id == problem_id).options(selectinload(Problem.testcases))
    )
    if not problem:
        raise HTTPException(status_code=404, detail="Problem not found")
    return ProblemOut.from_model(problem)


@app.post("/problems", response_model=ProblemOut, status_code=201)
def create_problem(payload: ProblemCreate, db: Session = Depends(get_db)):
    existing = db.scalar(select(Problem).where(Problem.slug == payload.slug))
    if existing:
        raise HTTPException(status_code=409, detail="Problem slug already exists")

    tests_dir = settings.data_dir / "problems" / payload.slug / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)

    problem = Problem(
        title=payload.title,
        slug=payload.slug,
        time_limit_ms=payload.time_limit_ms,
        description=payload.description,
        input_spec=payload.input_spec,
        output_spec=payload.output_spec,
        example_input=payload.example_input,
        example_output=payload.example_output,
    )
    db.add(problem)
    db.flush()

    for index, testcase in enumerate(payload.testcases, start=1):
        input_path = tests_dir / f"{index}.in"
        output_path = tests_dir / f"{index}.out"
        input_path.write_text(testcase.input, encoding="utf-8")
        output_path.write_text(testcase.output, encoding="utf-8")
        db.add(
            Testcase(
                problem_id=problem.id,
                order_index=index,
                input_path=str(input_path),
                output_path=str(output_path),
            )
        )

    db.commit()
    db.refresh(problem)
    problem = db.scalar(
        select(Problem).where(Problem.id == problem.id).options(selectinload(Problem.testcases))
    )
    return ProblemOut.from_model(problem)


@app.post("/submissions", response_model=SubmissionOut, status_code=202)
def create_submission(payload: SubmissionCreate, db: Session = Depends(get_db)):
    language = normalize_language(payload.language)

    problem = db.scalar(select(Problem).where(Problem.id == payload.problem_id))
    if not problem:
        raise HTTPException(status_code=404, detail="Problem not found")

    submission = Submission(
        problem_id=payload.problem_id,
        language=language,
        source_code=payload.source_code,
        status="QUEUED",
    )
    db.add(submission)
    db.commit()
    db.refresh(submission)

    queue = get_queue()
    queue.enqueue("worker.judge_submission.judge_submission", submission.id)
    return SubmissionOut.from_model(submission)


@app.get("/submissions/{submission_id}", response_model=SubmissionOut)
def get_submission(submission_id: int, db: Session = Depends(get_db)):
    submission = db.scalar(select(Submission).where(Submission.id == submission_id))
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    return SubmissionOut.from_model(submission)


@app.get("/problems/{problem_id}/submissions", response_model=list[SubmissionOut])
def list_problem_submissions(problem_id: int, db: Session = Depends(get_db)):
    problem = db.scalar(select(Problem).where(Problem.id == problem_id))
    if not problem:
        raise HTTPException(status_code=404, detail="Problem not found")

    submissions = db.scalars(
        select(Submission)
        .where(Submission.problem_id == problem_id)
        .order_by(Submission.created_at.desc(), Submission.id.desc())
    ).all()
    return [SubmissionOut.from_model(submission) for submission in submissions]
