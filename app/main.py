from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.auth import (
    authenticate_user,
    clear_session_cookies,
    create_user_session,
    get_current_user,
    get_session_from_request,
    hash_password,
    require_authenticated_user,
    require_csrf,
    require_problem_author_or_admin,
    revoke_session,
    set_session_cookies,
)
from app.bootstrap import init_db, init_storage, seed_admin_user, seed_example_problem
from app.db import SessionLocal, get_db
from app.languages import get_language, list_languages
from app.models import Problem, Submission, Testcase, User
from app.problem_assets import (
    CheckerCompileError,
    compile_checker,
    reset_problem_tests_directory,
)
from app.queue import get_queue
from app.schemas import (
    AuthUserOut,
    ExampleCreate,
    LanguageOut,
    LoginRequest,
    ProblemCreate,
    ProblemOut,
    RegisterRequest,
    SubmissionCreate,
    SubmissionOut,
    SubtaskInfoEntry,
    UserSummary,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_storage()
    init_db()
    with SessionLocal() as db:
        seed_admin_user(db)
        seed_example_problem(db)
    yield


app = FastAPI(title="Minimal OJ", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def attach_session(request: Request, call_next):
    with SessionLocal() as db:
        session = get_session_from_request(db, request)
        response = await call_next(request)
        if session and not getattr(request.state, "clear_session_cookies", False):
            set_session_cookies(response, request.state.raw_session_token, session.csrf_token)
        return response


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/auth/register", response_model=AuthUserOut, status_code=201)
def register(
    payload: RegisterRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    existing = db.scalar(select(User).where(User.username == payload.username))
    if existing:
        raise HTTPException(status_code=400, detail="Username is already taken")

    user = User(
        username=payload.username,
        password_hash=hash_password(payload.password),
        display_name=payload.display_name or payload.username,
        email=payload.email,
        role="user",
    )
    db.add(user)
    db.flush()
    raw_token, session = create_user_session(db, user, request)
    db.commit()
    db.refresh(user)
    set_session_cookies(response, raw_token, session.csrf_token)
    return AuthUserOut.from_model(user)


@app.post("/auth/login", response_model=AuthUserOut)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    user = authenticate_user(db, payload.username, payload.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    raw_token, session = create_user_session(db, user, request)
    db.commit()
    db.refresh(user)
    set_session_cookies(response, raw_token, session.csrf_token)
    return AuthUserOut.from_model(user)


@app.post("/auth/logout", status_code=204, dependencies=[Depends(require_csrf)])
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    revoke_session(db, request)
    request.state.clear_session_cookies = True
    clear_session_cookies(response)
    response.status_code = 204
    return response


@app.get("/auth/me", response_model=AuthUserOut | None)
def auth_me(current_user: User | None = Depends(get_current_user)):
    if not current_user:
        return None
    return AuthUserOut.from_model(current_user)


@app.get("/users/{user_id}", response_model=UserSummary)
def get_user(user_id: int, db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=404, detail="User not found")
    return UserSummary.from_model(user)


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
    problems = db.scalars(select(Problem).options(selectinload(Problem.testcases), selectinload(Problem.author))).all()
    return [ProblemOut.from_model(problem) for problem in problems]


@app.get("/problems/{problem_id}", response_model=ProblemOut)
def get_problem(problem_id: int, db: Session = Depends(get_db)):
    problem = db.scalar(
        select(Problem)
        .where(Problem.id == problem_id)
        .options(selectinload(Problem.testcases), selectinload(Problem.author))
    )
    if not problem:
        raise HTTPException(status_code=404, detail="Problem not found")
    return ProblemOut.from_model(problem)


def validate_subtask_info(payload: ProblemCreate) -> None:
    if not payload.use_subtask:
        return

    if not payload.subtask_info:
        raise HTTPException(
            status_code=400,
            detail="Subtask info is required when use_subtask is enabled",
        )

    testcase_count = len(payload.testcases)
    for subtask_id, subtask in payload.subtask_info.items():
        if not subtask.cases:
            raise HTTPException(
                status_code=400,
                detail=f"Subtask {subtask_id} must contain at least one testcase",
            )
        for case_id in subtask.cases:
            if case_id < 1 or case_id > testcase_count:
                raise HTTPException(
                    status_code=400,
                    detail=f"Subtask {subtask_id} references invalid testcase {case_id}",
                )


def populate_problem(problem: Problem, payload: ProblemCreate) -> None:
    problem.title = payload.title
    problem.slug = payload.slug
    problem.time_limit_ms = payload.time_limit_ms
    problem.memory_limit = payload.memory_limit
    problem.description = payload.description
    problem.input_spec = payload.input_spec
    problem.output_spec = payload.output_spec
    problem.examples = [example.model_dump() for example in payload.examples]
    problem.use_subtask = payload.use_subtask
    problem.subtask_info = {subtask_id: subtask.model_dump() for subtask_id, subtask in payload.subtask_info.items()}
    problem.checker_source_path = payload.checker_source_path


def problem_create_from_model(problem: Problem) -> ProblemCreate:
    testcases = []
    for testcase in sorted(problem.testcases, key=lambda item: item.order_index):
        with open(testcase.input_path, "r", encoding="utf-8") as input_file:
            testcase_input = input_file.read()
        with open(testcase.output_path, "r", encoding="utf-8") as output_file:
            testcase_output = output_file.read()
        testcases.append({"input": testcase_input, "output": testcase_output})

    return ProblemCreate(
        title=problem.title,
        slug=problem.slug,
        time_limit_ms=problem.time_limit_ms,
        memory_limit=problem.memory_limit,
        description=problem.description,
        input_spec=problem.input_spec,
        output_spec=problem.output_spec,
        examples=[ExampleCreate(**example) for example in problem.examples] if problem.examples else [],
        use_subtask=problem.use_subtask,
        subtask_info={subtask_id: SubtaskInfoEntry(**subtask) for subtask_id, subtask in problem.subtask_info.items()}
        if problem.subtask_info
        else {},  # type: ignore
        checker_source_path=problem.checker_source_path,
        testcases=testcases,
    )


def replace_problem_testcases(problem: Problem, payload: ProblemCreate, db: Session) -> None:
    tests_dir = reset_problem_tests_directory(problem.id)
    for testcase in list(problem.testcases):
        db.delete(testcase)
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


@app.post(
    "/problems",
    response_model=ProblemOut,
    status_code=201,
    dependencies=[Depends(require_csrf)],
)
def create_problem(
    payload: ProblemCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_authenticated_user),
):
    validate_subtask_info(payload)
    problem = Problem(author_id=current_user.id)
    populate_problem(problem, payload)
    db.add(problem)
    db.flush()
    replace_problem_testcases(problem, payload, db)
    try:
        compile_checker(problem)
    except CheckerCompileError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    db.commit()
    db.refresh(problem)
    problem = db.scalar(
        select(Problem)
        .where(Problem.id == problem.id)
        .options(selectinload(Problem.testcases), selectinload(Problem.author))
    )
    return ProblemOut.from_model(problem)


@app.get("/problems/{problem_id}/manage", response_model=ProblemCreate)
def get_problem_for_manage(
    problem_id: int,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user),
):
    problem = db.scalar(
        select(Problem)
        .where(Problem.id == problem_id)
        .options(selectinload(Problem.testcases), selectinload(Problem.author))
    )
    if not problem:
        raise HTTPException(status_code=404, detail="Problem not found")
    require_problem_author_or_admin(problem, current_user)
    return problem_create_from_model(problem)


@app.put(
    "/problems/{problem_id}",
    response_model=ProblemOut,
    dependencies=[Depends(require_csrf)],
)
def update_problem(
    problem_id: int,
    payload: ProblemCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    problem = db.scalar(
        select(Problem)
        .where(Problem.id == problem_id)
        .options(selectinload(Problem.testcases), selectinload(Problem.author))
    )
    if not problem:
        raise HTTPException(status_code=404, detail="Problem not found")
    require_problem_author_or_admin(problem, current_user)

    validate_subtask_info(payload)
    populate_problem(problem, payload)
    replace_problem_testcases(problem, payload, db)
    try:
        compile_checker(problem)
    except CheckerCompileError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    db.commit()
    db.refresh(problem)
    problem = db.scalar(
        select(Problem)
        .where(Problem.id == problem.id)
        .options(selectinload(Problem.testcases), selectinload(Problem.author))
    )
    return ProblemOut.from_model(problem)


@app.post(
    "/submissions",
    response_model=SubmissionOut,
    status_code=202,
    dependencies=[Depends(require_csrf)],
)
def create_submission(
    payload: SubmissionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_authenticated_user),
):
    language = normalize_language(payload.language)

    problem = db.scalar(select(Problem).where(Problem.id == payload.problem_id))
    if not problem:
        raise HTTPException(status_code=404, detail="Problem not found")

    submission = Submission(
        problem_id=payload.problem_id,
        user_id=current_user.id,
        language=language,
        source_code=payload.source_code,
        status="QUEUED",
    )
    db.add(submission)
    db.commit()
    db.refresh(submission)

    queue = get_queue()
    queue.enqueue("worker.judge_submission.judge_submission", submission.id)
    submission = db.scalar(
        select(Submission).where(Submission.id == submission.id).options(selectinload(Submission.user))
    )
    return SubmissionOut.from_model(submission, viewer_id=current_user.id)


@app.get("/submissions/{submission_id}", response_model=SubmissionOut)
def get_submission(
    submission_id: int,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user),
):
    submission = db.scalar(
        select(Submission).where(Submission.id == submission_id).options(selectinload(Submission.user))
    )
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    return SubmissionOut.from_model(submission, viewer_id=current_user.id if current_user else None)


@app.get("/problems/{problem_id}/submissions", response_model=list[SubmissionOut])
def list_problem_submissions(
    problem_id: int,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user),
):
    problem = db.scalar(select(Problem).where(Problem.id == problem_id))
    if not problem:
        raise HTTPException(status_code=404, detail="Problem not found")

    submissions = db.scalars(
        select(Submission)
        .where(Submission.problem_id == problem_id)
        .options(selectinload(Submission.user))
        .order_by(Submission.created_at.desc(), Submission.id.desc())
    ).all()
    viewer_id = current_user.id if current_user else None
    return [SubmissionOut.from_model(submission, viewer_id=viewer_id) for submission in submissions]
