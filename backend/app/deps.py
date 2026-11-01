"""FastAPI 의존성. 테스트에서는 app.dependency_overrides로 바꿔 끼운다."""

from functools import lru_cache

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from app.ai.client import AnthropicLLM, LLMClient
from app.config import Settings, get_settings
from app.db import get_db
from app.models import Group, Member
from app.places.catalog import Catalog, load_catalog_cached
from app.places.provider import ReservationProvider, build_provider
from app.services.availability import MemberSchedule
from app.timetable import busy_blocks


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
def _provider(name: str) -> ReservationProvider:
    return build_provider(name)


def get_provider(settings: Settings = Depends(get_settings)) -> ReservationProvider:
    return _provider(settings.reservation_provider)


def get_group(group_id: str, db: Session = Depends(get_db)) -> Group:
    group = db.get(Group, group_id)
    if group is None:
        raise HTTPException(404, "모임을 찾을 수 없어요.")
    return group


def get_member(
    member_id: str, group: Group = Depends(get_group), db: Session = Depends(get_db)
) -> Member:
    member = db.get(Member, member_id)
    if member is None or member.group_id != group.id:
        raise HTTPException(404, "팀원을 찾을 수 없어요.")
    return member


def member_schedules(group: Group) -> list[MemberSchedule]:
    return [
        MemberSchedule(
            member_id=m.id,
            name=m.name or "팀원",
            busy=busy_blocks(m.busy),
            busy_keys=tuple(m.busy),
        )
        for m in group.members
    ]
