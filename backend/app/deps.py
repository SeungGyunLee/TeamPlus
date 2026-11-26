"""FastAPI 의존성. 테스트에서는 app.dependency_overrides로 바꿔 끼운다."""

from functools import lru_cache

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.client import AnthropicLLM, LLMClient
from app.config import Settings, get_settings
from app.db import get_db
from app.models import AuthToken, Group, Member, User
from app.places.catalog import Catalog, load_catalog_cached
from app.places.provider import ReservationProvider, build_provider
from app.services.auth import token_hash
from app.services.availability import MemberSchedule
from app.services.mail import Mailer, build_mailer
from app.timetable import busy_blocks
from app.timeutil import as_kst, now_kst

# Swagger(/docs)에 'Authorize' 버튼이 생긴다. 앱은 Authorization: Bearer <토큰> 헤더를 보낸다.
bearer = HTTPBearer(auto_error=False, description="로그인 응답의 accessToken")


@lru_cache
def _llm(api_key: str, model: str, timeout: float) -> AnthropicLLM:
    return AnthropicLLM(api_key=api_key, model=model, timeout=timeout)


def get_llm(settings: Settings = Depends(get_settings)) -> LLMClient | None:
    if not settings.anthropic_api_key:
        return None
    return _llm(settings.anthropic_api_key, settings.llm_model, settings.llm_timeout_seconds)


def require_llm(llm: LLMClient | None = Depends(get_llm)) -> LLMClient:
    if llm is None:
        raise HTTPException(
            503, "ANTHROPIC_API_KEY가 설정되지 않았어요. backend/.env를 확인하세요."
        )
    return llm


def get_catalog(settings: Settings = Depends(get_settings)) -> Catalog:
    return load_catalog_cached(str(settings.places_file))


@lru_cache
def _mailer(
    backend: str,
    host: str | None,
    port: int,
    username: str | None,
    password: str | None,
    sender: str | None,
    security: str,
) -> Mailer:
    return build_mailer(
        backend,
        host=host,
        port=port,
        username=username,
        password=password,
        sender=sender,
        security=security,
    )


def get_mailer(settings: Settings = Depends(get_settings)) -> Mailer:
    return _mailer(
        settings.mail_backend,
        settings.smtp_host,
        settings.smtp_port,
        settings.smtp_username,
        settings.smtp_password,
        settings.mail_from,
        settings.smtp_security,
    )


@lru_cache
def _provider(
    name: str, status_url: str | None, map_url: str | None, cache: int, timeout: float
) -> ReservationProvider:
    # 서버가 떠 있는 동안 하나만 만든다 (집현전 캐시를 모든 요청이 같이 쓰도록)
    return build_provider(
        name, status_url=status_url, map_url=map_url, cache_seconds=cache, timeout=timeout
    )


def get_provider(settings: Settings = Depends(get_settings)) -> ReservationProvider:
    return _provider(
        settings.reservation_provider,
        settings.jiphyeonjeon_status_url,
        settings.jiphyeonjeon_map_url,
        settings.jiphyeonjeon_cache_seconds,
        settings.jiphyeonjeon_timeout_seconds,
    )


# ---------- 로그인 ----------
UNAUTHORIZED = HTTPException(401, "로그인이 필요해요.", headers={"WWW-Authenticate": "Bearer"})


def _user_from_token(db: Session, token: str) -> User | None:
    row = db.get(AuthToken, token_hash(token))
    if row is None:
        return None
    if as_kst(row.expires_at) <= now_kst():
        db.delete(row)
        db.commit()
        return None
    return db.get(User, row.user_id)


def get_optional_user(
    cred: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)
) -> User | None:
    if cred is None:
        return None
    user = _user_from_token(db, cred.credentials)
    if user is None:
        raise UNAUTHORIZED
    return user


def get_current_user(user: User | None = Depends(get_optional_user)) -> User:
    if user is None:
        raise UNAUTHORIZED
    return user


# ---------- 모임 권한 ----------
def my_membership(db: Session, group_id: str, user: User) -> Member | None:
    """이 사용자가 '참여완료' 상태로 들어가 있는 팀원 행"""
    return db.scalar(
        select(Member).where(
            Member.group_id == group_id, Member.user_id == user.id, Member.status == "joined"
        )
    )


def get_group(
    group_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> Group:
    """내가 참여한 모임만 보인다. 남의 모임은 있는지 없는지도 알리지 않는다 (404)."""
    group = db.get(Group, group_id)
    if group is None or my_membership(db, group_id, user) is None:
        raise HTTPException(404, "모임을 찾을 수 없어요.")
    return group


def get_member(
    member_id: str, group: Group = Depends(get_group), db: Session = Depends(get_db)
) -> Member:
    member = db.get(Member, member_id)
    if member is None or member.group_id != group.id:
        raise HTTPException(404, "팀원을 찾을 수 없어요.")
    return member


def joined_members(group: Group) -> list[Member]:
    return [m for m in group.members if m.status == "joined"]


def member_schedules(group: Group) -> list[MemberSchedule]:
    """공강·추천 계산 대상: 참여한 팀원만 (초대 '대기중'은 제외)"""
    return [
        MemberSchedule(
            member_id=m.id,
            name=m.name or "팀원",
            busy=busy_blocks(m.busy),
            busy_keys=tuple(m.busy),
        )
        for m in joined_members(group)
    ]
