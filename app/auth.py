from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from secrets import token_urlsafe

from fastapi import Depends, HTTPException, Request, Response, status
from passlib.context import CryptContext
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import Problem, User, UserSession

SESSION_COOKIE_NAME = "oj_session"
CSRF_COOKIE_NAME = "oj_csrf"
CSRF_HEADER_NAME = "X-CSRF-Token"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
pwd_context = CryptContext(
    schemes=["argon2"],
    deprecated="auto",
    argon2__time_cost=3,
    argon2__memory_cost=65536,
    argon2__parallelism=2,
)
fake_hash = pwd_context.hash("fake_password_for_timing")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def hash_session_token(token: str) -> str:
    return sha256(f"{settings.session_secret}:{token}".encode("utf-8")).hexdigest()


def new_session_expiry() -> datetime:
    return utc_now() + timedelta(seconds=settings.session_max_age)


def create_user_session(db: Session, user: User, request: Request) -> tuple[str, UserSession]:
    raw_token = token_urlsafe(32)
    csrf_token = token_urlsafe(24)
    session = UserSession(
        user_id=user.id,
        session_token_hash=hash_session_token(raw_token),
        csrf_token=csrf_token,
        expires_at=new_session_expiry(),
        last_seen_at=utc_now(),
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    db.add(session)
    db.flush()
    return raw_token, session


def set_session_cookies(response: Response, raw_token: str, csrf_token: str) -> None:
    response.set_cookie(
        SESSION_COOKIE_NAME,
        raw_token,
        max_age=settings.session_max_age,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )
    response.set_cookie(
        CSRF_COOKIE_NAME,
        csrf_token,
        max_age=settings.session_max_age,
        httponly=False,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )


def clear_session_cookies(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE_NAME, path="/", samesite="lax")
    response.delete_cookie(CSRF_COOKIE_NAME, path="/", samesite="lax")


def get_session_from_request(db: Session, request: Request) -> UserSession | None:
    cached_session = getattr(request.state, "current_session", None)
    if cached_session is not None:
        return cached_session

    raw_token = request.cookies.get(SESSION_COOKIE_NAME)
    if not raw_token:
        request.state.current_session = None
        return None

    session = db.scalar(
        select(UserSession)
        .where(UserSession.session_token_hash == hash_session_token(raw_token))
        .join(UserSession.user)
    )
    if not session:
        request.state.current_session = None
        return None

    now = utc_now()
    if session.expires_at <= now or not session.user.is_active:
        db.delete(session)
        db.commit()
        request.state.current_session = None
        return None

    session.last_seen_at = now
    session.expires_at = new_session_expiry()
    db.commit()
    db.refresh(session)
    request.state.current_session = session
    request.state.current_user = session.user
    request.state.raw_session_token = raw_token
    return session


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    cached_user = getattr(request.state, "current_user", None)
    if cached_user is not None:
        return cached_user
    session = get_session_from_request(db, request)
    if not session:
        return None
    return session.user


def require_authenticated_user(
    current_user: User | None = Depends(get_current_user),
) -> User:
    if not current_user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    return current_user


def require_problem_author_or_admin(
    problem: Problem,
    current_user: User | None,
) -> None:
    if not current_user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    if current_user.role == "admin":
        return
    if problem.author_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not allowed to modify this problem",
        )


def verify_csrf(request: Request, session: UserSession | None) -> None:
    if request.method in SAFE_METHODS:
        return
    if not session:
        return
    header_token = request.headers.get(CSRF_HEADER_NAME)
    if not header_token or header_token != session.csrf_token:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid CSRF token")


def require_csrf(
    request: Request,
    db: Session = Depends(get_db),
) -> None:
    verify_csrf(request, get_session_from_request(db, request))


def revoke_session(db: Session, request: Request) -> None:
    raw_token = request.cookies.get(SESSION_COOKIE_NAME)
    if not raw_token:
        return
    db.execute(delete(UserSession).where(UserSession.session_token_hash == hash_session_token(raw_token)))
    db.commit()


def authenticate_user(db: Session, username: str, password: str) -> User | None:
    user = db.scalar(select(User).where(User.username == username))

    valid = verify_password(password, user.password_hash if user else fake_hash)
    if not user or not valid or not user.is_active:
        return None
    return user
