"""로그인 (와이어프레임 1 최초 진입 → 2 이메일 입력 → 3A 로그인 / 3B 회원가입)
+ 비밀번호 찾기 (3A '비밀번호를 잊으셨나요?': 메일로 6자리 코드 → 코드와 새 비밀번호 입력).

이메일 + 비밀번호 + 닉네임만 받는다. 학번·실명은 받지 않는다.
로그인하면 accessToken을 주고, 앱은 이후 요청에 `Authorization: Bearer <토큰>`을 붙인다.
"""

import hmac
from datetime import timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import get_db
from app.deps import bearer, get_current_user, get_mailer
from app.models import AuthToken, Member, PasswordReset, User
from app.schemas import (
    AuthOut,
    EmailCheckOut,
    EmailCheckRequest,
    LoginRequest,
    MessageOut,
    PasswordResetConfirm,
    PasswordResetRequest,
    SignupRequest,
    UserOut,
    UserUpdate,
)
from app.services.auth import (
    hash_password,
    is_valid_email,
    new_reset_code,
    new_token,
    normalize_email,
    reset_code_hash,
    token_hash,
    verify_password,
)
from app.services.mail import Mailer, password_reset_mail, send_safely
from app.timeutil import as_kst, now_kst

router = APIRouter(prefix="/auth", tags=["로그인"])

MSG_BAD_EMAIL = "이메일 형식을 확인해 주세요."
MSG_LOGIN_FAILED = "이메일 또는 비밀번호가 맞지 않아요."
# 가입 여부와 상관없이 같은 문구 (가입한 이메일인지 여기서 알려주지 않음)
MSG_RESET_SENT = "가입된 이메일이면 인증 코드를 보냈어요. 메일함을 확인해 주세요."
MSG_RESET_BAD = "인증 코드가 맞지 않거나 만료됐어요."
MSG_RESET_LOCKED = "인증 코드를 여러 번 틀렸어요. 코드를 다시 받아 주세요."
RESET_RESEND_SECONDS = 60  # 같은 이메일로 코드 다시 받기까지 기다리는 시간
RESET_MAX_ATTEMPTS = 5


def _email_or_422(raw: str) -> str:
    email = normalize_email(raw)
    if not is_valid_email(email):
        raise HTTPException(422, MSG_BAD_EMAIL)
    return email


def _issue_token(db: Session, user: User, settings: Settings) -> AuthOut:
    token = new_token()
    expires = now_kst() + timedelta(days=settings.token_ttl_days)
    db.add(AuthToken(token_hash=token_hash(token), user_id=user.id, expires_at=expires))
    db.commit()
    return AuthOut(access_token=token, expires_at=expires, user=UserOut.model_validate(user))


@router.post("/check-email", response_model=EmailCheckOut, summary="가입된 이메일인지 확인 (2단계)")
def check_email(body: EmailCheckRequest, db: Session = Depends(get_db)):
    email = _email_or_422(body.email)
    exists = db.scalar(select(User.id).where(User.email == email)) is not None
    return EmailCheckOut(email=email, exists=exists)


@router.post("/signup", response_model=AuthOut, status_code=201, summary="회원가입 (3B)")
def signup(
    body: SignupRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    email = _email_or_422(body.email)
    if body.password_confirm is not None and body.password_confirm != body.password:
        raise HTTPException(400, "비밀번호가 서로 달라요.")
    if db.scalar(select(User.id).where(User.email == email)) is not None:
        raise HTTPException(409, "이미 가입된 이메일이에요. 로그인해 주세요.")
    user = User(
        email=email, password_hash=hash_password(body.password), nickname=body.nickname.strip()
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as e:  # 같은 이메일로 동시에 가입한 경우
        db.rollback()
        raise HTTPException(409, "이미 가입된 이메일이에요. 로그인해 주세요.") from e
    db.refresh(user)
    return _issue_token(db, user, settings)


@router.post("/login", response_model=AuthOut, summary="로그인 (3A)")
def login(
    body: LoginRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    user = db.scalar(select(User).where(User.email == normalize_email(body.email)))
    # 이메일이 없는지 비밀번호가 틀렸는지 구분해서 알려주지 않는다
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, MSG_LOGIN_FAILED)
    return _issue_token(db, user, settings)


@router.post("/logout", status_code=204, summary="로그아웃 (지금 토큰 무효화)")
def logout(
    cred: HTTPAuthorizationCredentials | None = Depends(bearer),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = db.get(AuthToken, token_hash(cred.credentials))
    if row is not None:
        db.delete(row)
        db.commit()
    return Response(status_code=204)


@router.get("/me", response_model=UserOut, summary="내 정보")
def me(user: User = Depends(get_current_user)):
    return user


@router.patch(
    "/me", response_model=UserOut, summary="닉네임 변경 (참여한 모임의 내 이름도 함께 바뀜)"
)
def update_me(
    body: UserUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    user.nickname = body.nickname.strip()
    db.execute(update(Member).where(Member.user_id == user.id).values(name=user.nickname))
    db.commit()
    db.refresh(user)
    return user


# ---------- 비밀번호 찾기 ----------
def _latest_reset(db: Session, user_id: str) -> PasswordReset | None:
    return db.scalar(
        select(PasswordReset)
        .where(PasswordReset.user_id == user_id)
        .order_by(PasswordReset.created_at.desc())
    )


@router.post(
    "/password-reset/request",
    response_model=MessageOut,
    status_code=202,
    summary="비밀번호 찾기 1: 이메일로 6자리 인증 코드 보내기",
)
def request_password_reset(
    body: PasswordResetRequest,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    mailer: Mailer = Depends(get_mailer),
):
    email = _email_or_422(body.email)
    user = db.scalar(select(User).where(User.email == email))
    if user is not None:
        now = now_kst()
        latest = _latest_reset(db, user.id)
        # 1분 안에 다시 누르면 새 코드를 만들지 않는다 (메일 폭탄 방지)
        if latest is None or (now - as_kst(latest.created_at)).total_seconds() >= (
            RESET_RESEND_SECONDS
        ):
            code = new_reset_code()
            db.execute(delete(PasswordReset).where(PasswordReset.user_id == user.id))
            db.add(
                PasswordReset(
                    user_id=user.id,
                    code_hash=reset_code_hash(user.id, code),
                    created_at=now,
                    expires_at=now + timedelta(minutes=settings.password_reset_minutes),
                )
            )
            db.commit()
            mail = password_reset_mail(email, code, settings.password_reset_minutes)
            background.add_task(send_safely, mailer, mail)
    return MessageOut(message=MSG_RESET_SENT)


@router.post(
    "/password-reset/confirm",
    response_model=AuthOut,
    summary="비밀번호 찾기 2: 인증 코드 + 새 비밀번호 → 바로 로그인",
)
def confirm_password_reset(
    body: PasswordResetConfirm,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    if body.new_password_confirm is not None and body.new_password_confirm != body.new_password:
        raise HTTPException(400, "비밀번호가 서로 달라요.")
    user = db.scalar(select(User).where(User.email == normalize_email(body.email)))
    row = _latest_reset(db, user.id) if user else None
    if row is None or as_kst(row.expires_at) <= now_kst():
        raise HTTPException(400, MSG_RESET_BAD)
    if row.attempts >= RESET_MAX_ATTEMPTS:
        raise HTTPException(400, MSG_RESET_LOCKED)
    if not hmac.compare_digest(row.code_hash, reset_code_hash(user.id, body.code)):
        row.attempts += 1
        db.commit()
        raise HTTPException(
            400, MSG_RESET_LOCKED if row.attempts >= RESET_MAX_ATTEMPTS else MSG_RESET_BAD
        )
    user.password_hash = hash_password(body.new_password)
    # 다른 기기의 로그인도 모두 끊는다
    db.execute(delete(AuthToken).where(AuthToken.user_id == user.id))
    db.execute(delete(PasswordReset).where(PasswordReset.user_id == user.id))
    db.commit()
    return _issue_token(db, user, settings)
