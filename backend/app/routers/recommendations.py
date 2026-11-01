"""AI 조건 해석(프롬프트 1)과 시간·장소 추천(코드 점수화 + 프롬프트 3)."""

from datetime import date, time

from fastapi import APIRouter, Depends, HTTPException
from pydantic.alias_generators import to_camel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai import service as ai
from app.ai.client import LLMClient, LLMError
from app.config import Settings, get_settings
from app.db import get_db
from app.deps import get_catalog, get_group, get_llm, get_provider, member_schedules, require_llm
from app.models import Group, Reservation
from app.occupancy import booked_map
from app.places.catalog import Catalog
from app.places.provider import ReservationProvider
from app.schemas import (
    CandidateOut,
    Conditions,
    ConditionsRequest,
    ConditionsResponse,
    ExcludedRoomOut,
    RecommendationRequest,
    RecommendationResponse,
    RoomOut,
)
from app.services import scoring
from app.services.booking import booking_window
from app.services.time_preference import parse_time_preference
from app.timetable import HOURS, hour_label
from app.timeutil import now_kst, today_kst

router = APIRouter(prefix="/groups/{group_id}", tags=["추천"])

# 추천 후보는 예약과 같은 1시간 슬롯 (09:00~19:00)
SLOT_MINUTES = 60
DAY_START = time(HOURS[0], 0)
DAY_END = time(HOURS[-1] + 1, 0)


def to_search_conditions(c: Conditions, today: date) -> scoring.SearchConditions:
    """AI가 뽑은 조건을 코드용 조건으로 바꾼다. '무관'·null은 조건 없음으로 본다."""
    return scoring.SearchConditions(
        capacity=c.capacity if c.capacity and c.capacity > 0 else None,
        noise_level=c.noise_level if c.noise_level in ("quiet", "normal") else None,
        needs_outlet=c.needs_outlet,
        needs_laptop_space=c.needs_laptop_space,
        room_type=c.room_type if c.room_type in ("study_room", "reading_room") else None,
        time_filter=parse_time_preference(c.time_preference, today),
    )


@router.post(
    "/conditions",
    response_model=ConditionsResponse,
    summary="자연어 조건 → 구조화 (프롬프트 1)",
)
def parse_conditions(
    body: ConditionsRequest,
    group: Group = Depends(get_group),
    llm: LLMClient = Depends(require_llm),
):
    try:
        parsed = ai.parse_conditions(llm, body.text)
    except LLMError as e:
        raise HTTPException(502, f"조건을 해석하지 못했어요: {e}") from e
    conditions = Conditions.from_parsed(parsed)
    if parsed.clarifying_question:
        return ConditionsResponse(
            type="question", conditions=conditions, question=parsed.clarifying_question
        )
    return ConditionsResponse(type="conditions", conditions=conditions)


@router.post(
    "/recommendations",
    response_model=RecommendationResponse,
    summary="집현전 시간·호실 추천 (코드 점수화 + 프롬프트 3 설명)",
)
def recommend(
    body: RecommendationRequest,
    group: Group = Depends(get_group),
    settings: Settings = Depends(get_settings),
    catalog: Catalog = Depends(get_catalog),
    provider: ReservationProvider = Depends(get_provider),
    llm: LLMClient | None = Depends(get_llm),
    db: Session = Depends(get_db),
):
    now = now_kst()
    first, last = booking_window(now)
    if body.date_from < first or body.date_to > last:
        raise HTTPException(422, "오늘부터 30일 이내의 날짜만 추천할 수 있어요.")

    members = member_schedules(group)
    # 이 모임이 이미 예약한 시간은 후보에서 뺀다 (같은 시간 다른 방 예약 불가)
    blocked = frozenset(
        (r.date, r.hour * 60)
        for r in db.scalars(
            select(Reservation).where(
                Reservation.group_id == group.id,
                Reservation.status == "active",
                Reservation.date >= body.date_from,
                Reservation.date <= body.date_to,
            )
        )
    )
    cond = to_search_conditions(body.conditions, today_kst())
    try:
        result = scoring.recommend(
            members,
            list(catalog.rooms),
            lambda rooms, day: booked_map(db, provider, rooms, day),
            cond,
            body.date_from,
            body.date_to,
            duration_minutes=SLOT_MINUTES,
            slot_minutes=SLOT_MINUTES,
            day_start=DAY_START,
            day_end=DAY_END,
            max_missing=settings.max_missing_members,
            limit=body.limit,
            not_before=now.replace(tzinfo=None),
            blocked=blocked,
        )
    except NotImplementedError as e:
        raise HTTPException(503, str(e)) from e

    payloads = [scoring.candidate_payload(c) for c in result.candidates]
    if body.with_reasons:
        reasons, source = ai.explain_candidates(llm, payloads)
    else:
        reasons, source = {}, "none"

    return RecommendationResponse(
        candidates=[
            CandidateOut(
                candidate_id=c.candidate_id,
                room=RoomOut.model_validate(c.evaluation.room),
                date=c.evaluation.date,
                hour=c.evaluation.start_min // 60,
                label=hour_label(c.evaluation.start_min // 60),
                score=c.evaluation.score,
                status=c.evaluation.status,
                available_member_ids=[m.member_id for m in c.evaluation.available],
                unavailable_member_ids=[m.member_id for m in c.evaluation.unavailable],
                conditions_met=c.evaluation.conditions_met,
                conflicts=c.evaluation.conflicts,
                reason=reasons.get(c.candidate_id),
            )
            for c in result.candidates
        ],
        excluded_rooms=[
            ExcludedRoomOut(room_id=e.room.id, room_name=e.room.full_name, reasons=e.reasons)
            for e in result.excluded_rooms
        ],
        excluded_windows={to_camel(k): v for k, v in result.excluded_windows.items()},
        reasons_source=source,
        time_preference_applied=cond.time_filter is not None,
    )
