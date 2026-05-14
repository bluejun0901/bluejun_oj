from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, Request, Response, UploadFile
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
    require_draft_author_or_admin,
    require_problem_author_or_admin,
    revoke_session,
    set_session_cookies,
)
from app.bootstrap import init_db, init_storage, seed_admin_user, seed_example_problem
from app.db import SessionLocal, get_db
from app.languages import get_language, list_languages
from app.models import DraftTestcase, Problem, ProblemDraft, Submission, Testcase, User
from app.problem_assets import (
    CheckerCompileError,
    compile_checker_from_root,
    draft_data_dir,
    problem_data_dir,
    read_testcase_text,
    read_text_asset,
    reset_tests_dir,
    tests_dir,
    write_checker_source,
)
from app.queue import get_queue
from app.schemas import (
    AuthUserOut,
    DraftCheckerOut,
    DraftCheckerUpdate,
    DraftCreate,
    DraftPreviewOut,
    DraftPreviewValidation,
    DraftStatementOut,
    DraftStatementUpdate,
    DraftSubtasksOut,
    DraftSubtasksUpdate,
    DraftSummaryOut,
    DraftTestcaseDetailOut,
    DraftTestcaseDetailUpdate,
    DraftTestcaseListOut,
    DraftTestcaseSummaryOut,
    ExampleCreate,
    LanguageOut,
    LoginRequest,
    ProblemOut,
    RegisterRequest,
    SubmissionCreate,
    SubmissionOut,
    SubtaskInfoEntry,
    UserSummary,
)

DEFAULT_CHECKER_SOURCE = """#include "testlib.h"

int main(int argc, char* argv[]) {
  registerTestlibCmd(argc, argv);
  std::string expected = ouf.readString();
  std::string actual = ans.readString();
  if (expected == actual) {
    quitf(_ok, "accepted");
  }
  quitf(_wa, "expected '%s' but found '%s'", expected.c_str(), actual.c_str());
}
"""


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


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def problem_query():
    return select(Problem).options(selectinload(Problem.testcases), selectinload(Problem.author))


def draft_query():
    return select(ProblemDraft).options(
        selectinload(ProblemDraft.author),
        selectinload(ProblemDraft.source_problem),
        selectinload(ProblemDraft.testcases),
    )


def normalize_language(language: str) -> str:
    try:
        return get_language(language).key
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def draft_summary(draft: ProblemDraft) -> DraftSummaryOut:
    return DraftSummaryOut.from_model(draft)


def get_draft_or_404(draft_id: int, db: Session) -> ProblemDraft:
    draft = db.scalar(draft_query().where(ProblemDraft.id == draft_id))
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    return draft


def get_problem_or_404(problem_id: int, db: Session) -> Problem:
    problem = db.scalar(problem_query().where(Problem.id == problem_id))
    if not problem:
        raise HTTPException(status_code=404, detail="Problem not found")
    return problem


def get_draft_testcase_or_404(draft: ProblemDraft, testcase_id: int) -> DraftTestcase:
    testcase = next((item for item in draft.testcases if item.id == testcase_id), None)
    if not testcase:
        raise HTTPException(status_code=404, detail="Draft testcase not found")
    return testcase


def ensure_slug_available(db: Session, slug: str, source_problem_id: int | None) -> None:
    slug = slug.strip()
    if not slug:
        return
    existing = db.scalar(select(Problem).where(Problem.slug == slug))
    if existing and existing.id != source_problem_id:
        raise HTTPException(status_code=400, detail=f"Slug '{slug}' is already used by problem #{existing.id}")


def validate_subtask_info(*, use_subtask: bool, subtask_info: dict[str, SubtaskInfoEntry], testcase_count: int) -> None:
    if not use_subtask:
        return
    if not subtask_info:
        raise HTTPException(status_code=400, detail="Subtask info is required when use_subtask is enabled")
    for subtask_id, subtask in subtask_info.items():
        if not subtask.cases:
            raise HTTPException(status_code=400, detail=f"Subtask {subtask_id} must contain at least one testcase")
        for case_id in subtask.cases:
            if case_id < 1 or case_id > testcase_count:
                raise HTTPException(
                    status_code=400,
                    detail=f"Subtask {subtask_id} references invalid testcase {case_id}",
                )


def validate_draft_for_publish(draft: ProblemDraft) -> list[DraftPreviewValidation]:
    validations: list[DraftPreviewValidation] = []
    if not draft.title.strip():
        validations.append(
            DraftPreviewValidation(code="missing_title", message="Title is required before publishing", level="error")
        )
    if not draft.slug.strip():
        validations.append(
            DraftPreviewValidation(code="missing_slug", message="Slug is required before publishing", level="error")
        )
    if not draft.description.strip():
        validations.append(
            DraftPreviewValidation(code="missing_description", message="Description is empty", level="warning")
        )
    if not draft.testcases:
        validations.append(
            DraftPreviewValidation(code="missing_testcases", message="At least one testcase is required", level="error")
        )
    validate_subtask_info(
        use_subtask=draft.use_subtask,
        subtask_info={key: SubtaskInfoEntry(**value) for key, value in (draft.subtask_info or {}).items()},
        testcase_count=len(draft.testcases),
    )
    if not read_text_asset(draft.checker_source_path).strip():
        validations.append(
            DraftPreviewValidation(code="missing_checker", message="Checker source is empty", level="error")
        )
    return validations


def draft_statement_out(draft: ProblemDraft) -> DraftStatementOut:
    return DraftStatementOut(
        summary=draft_summary(draft),
        title=draft.title,
        slug=draft.slug,
        time_limit_ms=draft.time_limit_ms,
        memory_limit=draft.memory_limit,
        description=draft.description,
        input_spec=draft.input_spec,
        output_spec=draft.output_spec,
        examples=[ExampleCreate(**example) for example in (draft.examples or [])],
    )


def draft_subtasks_out(draft: ProblemDraft) -> DraftSubtasksOut:
    return DraftSubtasksOut(
        summary=draft_summary(draft),
        use_subtask=draft.use_subtask,
        subtask_info={key: SubtaskInfoEntry(**value) for key, value in (draft.subtask_info or {}).items()},
    )


def draft_checker_out(draft: ProblemDraft) -> DraftCheckerOut:
    return DraftCheckerOut(
        summary=draft_summary(draft),
        checker_source=read_text_asset(draft.checker_source_path),
        checker_source_path=draft.checker_source_path,
    )


def draft_testcase_detail_out(testcase: DraftTestcase) -> DraftTestcaseDetailOut:
    contents = read_testcase_text(testcase.input_path, testcase.output_path)
    return DraftTestcaseDetailOut(
        id=testcase.id,
        order_index=testcase.order_index,
        name=testcase.name,
        input=contents["input"],
        output=contents["output"],
        input_path=testcase.input_path,
        output_path=testcase.output_path,
    )


def problem_out_from_draft(draft: ProblemDraft) -> ProblemOut:
    return ProblemOut(
        id=draft.source_problem_id or draft.id,
        author=UserSummary.from_model(draft.author),
        title=draft.title,
        slug=draft.slug,
        time_limit_ms=draft.time_limit_ms,
        memory_limit=draft.memory_limit,
        description=draft.description,
        input_spec=draft.input_spec,
        output_spec=draft.output_spec,
        examples=[ExampleCreate(**example) for example in (draft.examples or [])],
        use_subtask=draft.use_subtask,
        subtask_info={key: SubtaskInfoEntry(**value) for key, value in (draft.subtask_info or {}).items()},
        testcase_count=len(draft.testcases),
    )


def populate_problem_metadata_from_draft(problem: Problem, draft: ProblemDraft) -> None:
    problem.title = draft.title.strip()
    problem.slug = draft.slug.strip()
    problem.time_limit_ms = draft.time_limit_ms
    problem.memory_limit = draft.memory_limit
    problem.description = draft.description
    problem.input_spec = draft.input_spec
    problem.output_spec = draft.output_spec
    problem.examples = list(draft.examples or [])
    problem.use_subtask = draft.use_subtask
    problem.subtask_info = dict(draft.subtask_info or {})


def copy_problem_to_draft(source_problem: Problem, draft: ProblemDraft, db: Session) -> None:
    draft.title = source_problem.title
    draft.slug = source_problem.slug
    draft.time_limit_ms = source_problem.time_limit_ms
    draft.memory_limit = source_problem.memory_limit
    draft.description = source_problem.description
    draft.input_spec = source_problem.input_spec
    draft.output_spec = source_problem.output_spec
    draft.examples = list(source_problem.examples or [])
    draft.use_subtask = source_problem.use_subtask
    draft.subtask_info = dict(source_problem.subtask_info or {})
    draft.checker_source_path = write_checker_source(
        draft_data_dir(draft.id),
        read_text_asset(source_problem.checker_source_path) or DEFAULT_CHECKER_SOURCE,
    )
    reset_tests_dir(draft_data_dir(draft.id))
    for testcase in list(draft.testcases):
        db.delete(testcase)
    db.flush()
    for source_case in sorted(source_problem.testcases, key=lambda item: item.order_index):
        contents = read_testcase_text(source_case.input_path, source_case.output_path)
        target_dir = tests_dir(draft_data_dir(draft.id))
        input_path = target_dir / f"{source_case.order_index}.in"
        output_path = target_dir / f"{source_case.order_index}.out"
        input_path.write_text(contents["input"], encoding="utf-8")
        output_path.write_text(contents["output"], encoding="utf-8")
        db.add(
            DraftTestcase(
                draft_id=draft.id,
                order_index=source_case.order_index,
                name=source_case.name,
                input_path=str(input_path),
                output_path=str(output_path),
            )
        )


def replace_problem_testcases_from_draft(problem: Problem, draft: ProblemDraft, db: Session) -> None:
    target_dir = reset_tests_dir(problem_data_dir(problem.id))
    for testcase in list(problem.testcases):
        db.delete(testcase)
    db.flush()
    for source_case in sorted(draft.testcases, key=lambda item: item.order_index):
        contents = read_testcase_text(source_case.input_path, source_case.output_path)
        input_path = target_dir / f"{source_case.order_index}.in"
        output_path = target_dir / f"{source_case.order_index}.out"
        input_path.write_text(contents["input"], encoding="utf-8")
        output_path.write_text(contents["output"], encoding="utf-8")
        db.add(
            Testcase(
                problem_id=problem.id,
                order_index=source_case.order_index,
                name=source_case.name,
                input_path=str(input_path),
                output_path=str(output_path),
            )
        )


def testcase_pair_key(filename: str) -> tuple[str, str]:
    if filename.endswith(".in"):
        return filename[:-3], "input"
    if filename.endswith(".out"):
        return filename[:-4], "output"
    if filename.endswith(".a"):
        return filename[:-2], "output"
    return filename, "input"


async def import_testcase_files(draft: ProblemDraft, files: list[UploadFile], db: Session) -> None:
    grouped: dict[str, dict[str, UploadFile | None]] = {}
    for file in files:
        key, kind = testcase_pair_key(file.filename or "")
        bucket = grouped.setdefault(key, {"input": None, "output": None})
        if bucket[kind] is not None:
            raise HTTPException(status_code=400, detail=f"Duplicate testcase file for '{key}'")
        bucket[kind] = file

    ordered_keys = sorted(grouped.keys(), key=lambda value: value.lower())
    target_dir = reset_tests_dir(draft_data_dir(draft.id))
    for testcase in list(draft.testcases):
        db.delete(testcase)
    db.flush()

    for index, key in enumerate(ordered_keys, start=1):
        pair = grouped[key]
        if pair["input"] is None or pair["output"] is None:
            raise HTTPException(status_code=400, detail=f"Missing testcase pair for '{key}'")
        input_text = (await pair["input"].read()).decode("utf-8")
        output_text = (await pair["output"].read()).decode("utf-8")
        input_path = target_dir / f"{index}.in"
        output_path = target_dir / f"{index}.out"
        input_path.write_text(input_text, encoding="utf-8")
        output_path.write_text(output_text, encoding="utf-8")
        db.add(
            DraftTestcase(
                draft_id=draft.id,
                order_index=index,
                name=key or f"case-{index}",
                input_path=str(input_path),
                output_path=str(output_path),
            )
        )


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/auth/register", response_model=AuthUserOut, status_code=201)
def register(payload: RegisterRequest, request: Request, response: Response, db: Session = Depends(get_db)):
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
def login(payload: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    user = authenticate_user(db, payload.username, payload.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    raw_token, session = create_user_session(db, user, request)
    db.commit()
    db.refresh(user)
    set_session_cookies(response, raw_token, session.csrf_token)
    return AuthUserOut.from_model(user)


@app.post("/auth/logout", status_code=204, dependencies=[Depends(require_csrf)])
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
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


@app.get("/languages", response_model=list[LanguageOut])
def get_languages():
    return [LanguageOut.from_spec(spec) for spec in list_languages()]


@app.get("/problems", response_model=list[ProblemOut])
def list_problems(db: Session = Depends(get_db)):
    problems = db.scalars(problem_query()).all()
    return [ProblemOut.from_model(problem) for problem in problems]


@app.get("/problems/{problem_id}", response_model=ProblemOut)
def get_problem(problem_id: int, db: Session = Depends(get_db)):
    return ProblemOut.from_model(get_problem_or_404(problem_id, db))


@app.get("/drafts", response_model=list[DraftSummaryOut])
def list_drafts(db: Session = Depends(get_db), current_user: User = Depends(require_authenticated_user)):
    query = draft_query().order_by(ProblemDraft.updated_at.desc(), ProblemDraft.id.desc())
    if current_user.role != "admin":
        query = query.where(ProblemDraft.author_id == current_user.id)
    drafts = db.scalars(query).all()
    return [draft_summary(draft) for draft in drafts]


@app.post("/drafts", response_model=DraftSummaryOut, status_code=201, dependencies=[Depends(require_csrf)])
def create_draft(
    payload: DraftCreate, db: Session = Depends(get_db), current_user: User = Depends(require_authenticated_user)
):
    source_problem = None
    if payload.source_problem_id is not None:
        source_problem = get_problem_or_404(payload.source_problem_id, db)
        require_problem_author_or_admin(source_problem, current_user)

    draft = ProblemDraft(
        author_id=current_user.id,
        source_problem_id=payload.source_problem_id,
        title="",
        slug="",
        time_limit_ms=1000,
        memory_limit=256,
        description="",
        input_spec="",
        output_spec="",
        examples=[],
        use_subtask=False,
        subtask_info={},
    )
    db.add(draft)
    db.flush()
    if source_problem:
        copy_problem_to_draft(source_problem, draft, db)
    else:
        draft.checker_source_path = write_checker_source(draft_data_dir(draft.id), DEFAULT_CHECKER_SOURCE)
        reset_tests_dir(draft_data_dir(draft.id))
    db.commit()
    draft = get_draft_or_404(draft.id, db)
    return draft_summary(draft)


@app.post(
    "/problems/{problem_id}/drafts",
    response_model=DraftSummaryOut,
    status_code=201,
    dependencies=[Depends(require_csrf)],
)
def create_problem_edit_draft(
    problem_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_authenticated_user),
):
    return create_draft(DraftCreate(source_problem_id=problem_id), db, current_user)


@app.get("/drafts/{draft_id}", response_model=DraftSummaryOut)
def get_draft_summary(
    draft_id: int,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user),
):
    draft = get_draft_or_404(draft_id, db)
    require_draft_author_or_admin(draft, current_user)
    return draft_summary(draft)


@app.get("/drafts/{draft_id}/statement", response_model=DraftStatementOut)
def get_draft_statement(
    draft_id: int,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user),
):
    draft = get_draft_or_404(draft_id, db)
    require_draft_author_or_admin(draft, current_user)
    return draft_statement_out(draft)


@app.put("/drafts/{draft_id}/statement", response_model=DraftStatementOut, dependencies=[Depends(require_csrf)])
def update_draft_statement(
    draft_id: int,
    payload: DraftStatementUpdate,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user),
):
    draft = get_draft_or_404(draft_id, db)
    require_draft_author_or_admin(draft, current_user)
    draft.title = payload.title
    draft.slug = payload.slug
    draft.time_limit_ms = payload.time_limit_ms
    draft.memory_limit = payload.memory_limit
    draft.description = payload.description
    draft.input_spec = payload.input_spec
    draft.output_spec = payload.output_spec
    draft.examples = [example.model_dump() for example in payload.examples]
    db.commit()
    return draft_statement_out(get_draft_or_404(draft_id, db))


@app.get("/drafts/{draft_id}/subtasks", response_model=DraftSubtasksOut)
def get_draft_subtasks(
    draft_id: int,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user),
):
    draft = get_draft_or_404(draft_id, db)
    require_draft_author_or_admin(draft, current_user)
    return draft_subtasks_out(draft)


@app.put("/drafts/{draft_id}/subtasks", response_model=DraftSubtasksOut, dependencies=[Depends(require_csrf)])
def update_draft_subtasks(
    draft_id: int,
    payload: DraftSubtasksUpdate,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user),
):
    draft = get_draft_or_404(draft_id, db)
    require_draft_author_or_admin(draft, current_user)
    validate_subtask_info(
        use_subtask=payload.use_subtask,
        subtask_info=payload.subtask_info,
        testcase_count=len(draft.testcases),
    )
    draft.use_subtask = payload.use_subtask
    draft.subtask_info = {key: value.model_dump() for key, value in payload.subtask_info.items()}
    db.commit()
    return draft_subtasks_out(get_draft_or_404(draft_id, db))


@app.get("/drafts/{draft_id}/checker", response_model=DraftCheckerOut)
def get_draft_checker(
    draft_id: int,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user),
):
    draft = get_draft_or_404(draft_id, db)
    require_draft_author_or_admin(draft, current_user)
    return draft_checker_out(draft)


@app.put("/drafts/{draft_id}/checker", response_model=DraftCheckerOut, dependencies=[Depends(require_csrf)])
def update_draft_checker(
    draft_id: int,
    payload: DraftCheckerUpdate,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user),
):
    draft = get_draft_or_404(draft_id, db)
    require_draft_author_or_admin(draft, current_user)
    draft.checker_source_path = write_checker_source(draft_data_dir(draft.id), payload.checker_source)
    db.commit()
    return draft_checker_out(get_draft_or_404(draft_id, db))


@app.get("/drafts/{draft_id}/testcases", response_model=DraftTestcaseListOut)
def list_draft_testcases(
    draft_id: int,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user),
):
    draft = get_draft_or_404(draft_id, db)
    require_draft_author_or_admin(draft, current_user)
    return DraftTestcaseListOut(
        summary=draft_summary(draft),
        items=[DraftTestcaseSummaryOut.from_model(testcase) for testcase in draft.testcases],
    )


@app.post(
    "/drafts/{draft_id}/testcases/import", response_model=DraftTestcaseListOut, dependencies=[Depends(require_csrf)]
)
async def upload_draft_testcases(
    draft_id: int,
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user),
):
    draft = get_draft_or_404(draft_id, db)
    require_draft_author_or_admin(draft, current_user)
    await import_testcase_files(draft, files, db)
    db.commit()
    draft = get_draft_or_404(draft_id, db)
    return DraftTestcaseListOut(
        summary=draft_summary(draft),
        items=[DraftTestcaseSummaryOut.from_model(testcase) for testcase in draft.testcases],
    )


@app.get("/drafts/{draft_id}/testcases/{testcase_id}", response_model=DraftTestcaseDetailOut)
def get_draft_testcase_detail(
    draft_id: int,
    testcase_id: int,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user),
):
    draft = get_draft_or_404(draft_id, db)
    require_draft_author_or_admin(draft, current_user)
    return draft_testcase_detail_out(get_draft_testcase_or_404(draft, testcase_id))


@app.put(
    "/drafts/{draft_id}/testcases/{testcase_id}",
    response_model=DraftTestcaseDetailOut,
    dependencies=[Depends(require_csrf)],
)
def update_draft_testcase_detail(
    draft_id: int,
    testcase_id: int,
    payload: DraftTestcaseDetailUpdate,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user),
):
    draft = get_draft_or_404(draft_id, db)
    require_draft_author_or_admin(draft, current_user)
    testcase = get_draft_testcase_or_404(draft, testcase_id)
    testcase.name = payload.name
    Path(testcase.input_path).write_text(payload.input, encoding="utf-8")
    Path(testcase.output_path).write_text(payload.output, encoding="utf-8")
    db.commit()
    return draft_testcase_detail_out(get_draft_testcase_or_404(get_draft_or_404(draft_id, db), testcase_id))


@app.post("/drafts/{draft_id}/preview", response_model=DraftPreviewOut, dependencies=[Depends(require_csrf)])
def preview_draft(
    draft_id: int,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user),
):
    draft = get_draft_or_404(draft_id, db)
    require_draft_author_or_admin(draft, current_user)
    validations = validate_draft_for_publish(draft)
    slug_conflict = db.scalar(select(Problem).where(Problem.slug == draft.slug))
    if slug_conflict and slug_conflict.id != draft.source_problem_id:
        validations.append(
            DraftPreviewValidation(
                code="slug_conflict",
                message=f"Slug '{draft.slug}' is already used by problem #{slug_conflict.id}",
                level="error",
            )
        )
    try:
        compile_checker_from_root(draft_data_dir(draft.id))
        checker_compiles = True
        checker_error = None
    except CheckerCompileError as exc:
        checker_compiles = False
        checker_error = str(exc)
        validations.append(
            DraftPreviewValidation(
                code="checker_compile_error",
                message="checker.cpp does not compile",
                level="error",
            )
        )
    return DraftPreviewOut(
        draft=draft_summary(draft),
        problem=problem_out_from_draft(draft),
        checker_compiles=checker_compiles,
        checker_error=checker_error,
        validations=validations,
    )


@app.post("/drafts/{draft_id}/publish", response_model=ProblemOut, dependencies=[Depends(require_csrf)])
def publish_draft(
    draft_id: int,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user),
):
    draft = get_draft_or_404(draft_id, db)
    require_draft_author_or_admin(draft, current_user)
    validations = validate_draft_for_publish(draft)
    blocking = [item for item in validations if item.level == "error"]
    if blocking:
        raise HTTPException(status_code=400, detail=blocking[0].message)
    ensure_slug_available(db, draft.slug, draft.source_problem_id)

    if draft.source_problem_id is not None:
        problem = get_problem_or_404(draft.source_problem_id, db)
        require_problem_author_or_admin(problem, current_user)
    else:
        problem = Problem(
            author_id=draft.author_id,
            title=draft.title,
            slug=draft.slug,
            time_limit_ms=draft.time_limit_ms,
            memory_limit=draft.memory_limit,
            description=draft.description,
            input_spec=draft.input_spec,
            output_spec=draft.output_spec,
            examples=list(draft.examples or []),
            use_subtask=draft.use_subtask,
            subtask_info=dict(draft.subtask_info or {}),
        )
        db.add(problem)
        db.flush()
        draft.source_problem_id = problem.id

    populate_problem_metadata_from_draft(problem, draft)
    replace_problem_testcases_from_draft(problem, draft, db)
    problem.checker_source_path = write_checker_source(
        problem_data_dir(problem.id), read_text_asset(draft.checker_source_path)
    )
    try:
        compile_checker_from_root(problem_data_dir(problem.id))
    except CheckerCompileError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    draft.status = "published"
    draft.published_at = now_utc()
    db.commit()
    return ProblemOut.from_model(get_problem_or_404(problem.id, db))


@app.post("/submissions", response_model=SubmissionOut, status_code=202, dependencies=[Depends(require_csrf)])
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
