"""API 요청·응답 형식.

프론트(TypeScript)와 같은 camelCase로 주고받는다. 예: inviteCode, groupId, updatedAt
(요청은 snake_case로 보내도 받아준다.)
필드 구성은 frontend/src/domain/model.ts의 Group·Member·Place·Room과 맞춘다.
"""

from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic.alias_generators import to_camel

from app.ai.schemas import Milestone, ParsedConditions
from app.timetable import parse_slot_key
from app.timeutil import as_kst


def _with_tz(d: datetime) -> datetime:
    # SQLite는 시간대 없이, PostgreSQL은 UTC로 돌려준다. 응답은 항상 KST(+09:00)로 맞춘다.
    return as_kst(d)


# 응답 시각은 항상 시간대 포함 (예: 2026-11-14T20:13:19+09:00). 프론트 new Date()로 바로 읽힌다.
Timestamp = Annotated[datetime, AfterValidator(_with_tz)]


class ApiModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, from_attributes=True)


def _check_slot_keys(keys: list[str]) -> list[str]:
    for k in keys:
        parse_slot_key(k)  # 형식이 틀리면 ValueError → 422
    return sorted(set(keys), key=parse_slot_key)


# ---------- 로그인 (와이어프레임 1~3B) ----------
class EmailCheckRequest(ApiModel):
    email: str = Field(max_length=254)


class EmailCheckOut(ApiModel):
    email: str
    # true면 3A 로그인, false면 3B 회원가입 화면
    exists: bool


class SignupRequest(ApiModel):
    email: str = Field(max_length=254)
    password: str = Field(min_length=8, max_length=128)
    # 보내면 서버에서도 password와 같은지 확인한다 (프론트에서만 확인해도 됨)
    password_confirm: str | None = None
    nickname: str = Field(min_length=1, max_length=30)


class PasswordResetRequest(ApiModel):
    email: str = Field(max_length=254)


class PasswordResetConfirm(ApiModel):
    email: str = Field(max_length=254)
    # 메일로 받은 6자리 숫자
    code: str = Field(pattern=r"^\d{6}$")
    new_password: str = Field(min_length=8, max_length=128)
    # 보내면 서버에서도 new_password와 같은지 확인한다
    new_password_confirm: str | None = None


class MessageOut(ApiModel):
    message: str


class LoginRequest(ApiModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=128)


class UserOut(ApiModel):
    id: str
    email: str
    nickname: str
    created_at: Timestamp


class UserUpdate(ApiModel):
    nickname: str = Field(min_length=1, max_length=30)


class AuthOut(ApiModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_at: Timestamp
    user: UserOut


# ---------- 모임·팀원 ----------
class MemberOut(ApiModel):
    id: str
    name: str
    # 계정이 연결된 팀원이면 그 사용자 id. 내 userId와 같으면 화면에 '나'
    user_id: str | None = None
    email: str | None = None
    # joined = 참여완료(또는 이름만 있는 팀원), invited = 초대 대기중
    status: Literal["joined", "invited"]
    # 수업 있는 블록 키. "0-0" = 월요일 1교시
    busy: list[str]


class GroupOut(ApiModel):
    id: str
    name: str
    # 모임을 만든 사용자 id (모임 삭제 권한)
    owner_id: str
    # 프론트 Group 형식 유지용. 초대는 이메일로 하므로 항상 null
    invite_code: str | None
    members: list[MemberOut]
    updated_at: Timestamp


class GroupCreate(ApiModel):
    name: str = Field(default="새로운 모임", max_length=100)
    # 만든 사람은 자동으로 참여. 계정 없는 팀원을 이름만으로 함께 넣고 싶을 때만 사용
    member_names: list[str] = Field(default_factory=list, max_length=11)


class InviteCreate(ApiModel):
    email: str = Field(max_length=254)


class InviteOut(ApiModel):
    """나에게 온 초대 (내 이메일로 초대된 '대기중' 팀원 행)"""

    member_id: str
    group_id: str
    group_name: str
    # 초대한 사람 닉네임 (탈퇴 등으로 알 수 없으면 null)
    inviter_name: str | None
    # 참여한 팀원 수 (초대 대기중은 세지 않음)
    member_count: int


class GroupUpdate(ApiModel):
    name: str = Field(max_length=100)


class MemberCreate(ApiModel):
    name: str = Field(default="", max_length=50)
    busy: list[str] = Field(default_factory=list)

    _keys = field_validator("busy")(_check_slot_keys)


class MemberUpdate(ApiModel):
    """이름이나 시간표 중 바꿀 것만 보낸다. busy는 전체 목록으로 교체."""

    name: str | None = Field(default=None, max_length=50)
    busy: list[str] | None = None

    @field_validator("busy")
    @classmethod
    def _keys(cls, v):
        return None if v is None else _check_slot_keys(v)


# ---------- 공통 공강 (월~금 × 6교시) ----------
class BlockOut(ApiModel):
    key: str
    day: int
    period: int
    period_label: str  # 09:00–10:30
    count: int
    total: int
    level: Literal["full", "partial", "none"]
    available_member_ids: list[str]
    unavailable_member_ids: list[str]


class AvailabilityOut(ApiModel):
    group_id: str
    total: int
    # 전원 참석 가능한 블록 수 (홈 화면 '이번 주의 공통 공강')
    full_count: int
    # 참석 가능 인원 많은 순 → 요일순 → 교시순 (프론트 rankedAvailability와 같은 순서)
    blocks: list[BlockOut]


# ---------- 장소·호실 ----------
class RoomOut(ApiModel):
    id: str
    place_id: str
    name: str
    full_name: str
    capacity: int
    has_outlet: bool
    noise_level: Literal["quiet", "normal"]
    laptop_space: bool


SlotState = Literal["past", "occupied", "available"]


class SlotOut(ApiModel):
    hour: int
    label: str  # 16:00–17:00
    # 지난 시간 > 예약됨(도서관 예약 현황) > 예약 가능
    state: SlotState
    selectable: bool


class RoomAvailabilityOut(ApiModel):
    room_id: str
    room_name: str
    capacity: int
    # groupId를 주면 그 모임 인원이 들어갈 수 있는지
    fits_group: bool | None
    slots: list[SlotOut]


# ---------- 조건 해석 (프롬프트 1) ----------
class ConditionsRequest(ApiModel):
    text: str = Field(min_length=1, max_length=500)


class Conditions(ApiModel):
    """AI가 해석한 조건.

    /conditions 응답을 그대로 /recommendations에 넣거나, 프론트에서 고쳐서 넣는다.
    """

    capacity: int | None = Field(default=None, ge=1)
    noise_level: Literal["quiet", "normal", "무관"] | None = None
    needs_outlet: bool | None = None
    needs_laptop_space: bool | None = None
    room_type: Literal["study_room", "reading_room", "무관"] | None = None
    time_preference: str | None = None
    clarifying_question: str | None = None

    @classmethod
    def from_parsed(cls, p: ParsedConditions) -> "Conditions":
        return cls.model_validate(p.model_dump())


class ConditionsResponse(ApiModel):
    # question이면 추천 전에 question을 사용자에게 보여주고 답을 받아 다시 요청한다.
    type: Literal["conditions", "question"]
    conditions: Conditions
    question: str | None = None


# ---------- 추천 (점수화 + 프롬프트 3) ----------
class RecommendationRequest(ApiModel):
    conditions: Conditions = Field(default_factory=Conditions)
    date_from: date
    date_to: date
    limit: int = Field(default=5, ge=1, le=20)
    with_reasons: bool = True

    @model_validator(mode="after")
    def _check_range(self):
        if self.date_to < self.date_from:
            raise ValueError("dateTo는 dateFrom보다 같거나 늦어야 해요.")
        return self


class CandidateOut(ApiModel):
    candidate_id: str
    room: RoomOut
    date: date
    hour: int  # 예약 API에 그대로 넣을 수 있는 시작 시각
    label: str  # 16:00–17:00
    score: int
    status: Literal["green", "orange"]
    available_member_ids: list[str]
    unavailable_member_ids: list[str]
    conditions_met: list[str]
    conflicts: list[str]
    reason: str | None = None


class ExcludedRoomOut(ApiModel):
    room_id: str
    room_name: str
    reasons: list[str]


class RecommendationResponse(ApiModel):
    candidates: list[CandidateOut]
    excluded_rooms: list[ExcludedRoomOut]
    # 시간대 단위로 빠진 개수
    # booked(예약됨), notEnoughMembers(인원 부족)
    excluded_windows: dict[str, int]
    # 실제로 찾아본 기간. 요청 기간을 오늘부터 7일 안으로 자른 값
    date_from: date
    date_to: date
    # 추천 이유 출처: ai | partial(일부 기본 문구) | fallback(전부 기본 문구) | none(요청 안 함)
    reasons_source: Literal["ai", "partial", "fallback", "none"]
    # timePreference를 코드가 알아듣고 시간 필터로 적용했는지
    time_preference_applied: bool


# ---------- 과제·회의 단계 (프롬프트 2 + 단계 배치) ----------
class AssignmentCreate(ApiModel):
    notice_text: str = Field(min_length=1, max_length=5000)
    title: str | None = Field(default=None, max_length=200)
    # 사용자가 직접 넣으면 AI가 뽑은 값보다 우선한다.
    final_deadline: date | None = None


class DeadlineUpdate(ApiModel):
    final_deadline: date


class StageOut(ApiModel):
    position: int
    name: str
    purpose: str
    priority: str
    window_start: date | None
    window_end: date | None
    anchored_to: str | None
    dropped: bool


class AssignmentOut(ApiModel):
    id: int
    title: str | None
    final_deadline: date | None
    deadline_source: Literal["user", "ai"] | None
    # ok | missing(마감일 없음) | past(이미 지남). ok가 아니면 단계 날짜가 비어 있다.
    deadline_status: Literal["ok", "missing", "past"]
    deliverable_type: str
    milestones: list[Milestone]
    stages: list[StageOut]
