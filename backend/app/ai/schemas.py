"""LLM 응답 스키마. structured outputs로 이 형식을 강제한다 (코드블록 벗기기 불필요).

필드 이름과 값은 핸드오프 스키마를 그대로 따른다 ('무관' 포함).
structured outputs가 지원하지 않는 제약(minimum, maxLength 등)은 넣지 않는다.
"""

from datetime import date as Date
from typing import Literal

from pydantic import BaseModel, field_validator


def _lower(v):
    return v.strip().lower() if isinstance(v, str) else v


# 프롬프트 1
class ParsedConditions(BaseModel):
    capacity: int | None
    noise_level: Literal["quiet", "normal", "무관"] | None
    needs_outlet: bool | None
    needs_laptop_space: bool | None
    room_type: Literal["study_room", "reading_room", "무관"] | None
    time_preference: str | None
    clarifying_question: str | None

    _lower_enums = field_validator("noise_level", "room_type", mode="before")(_lower)


# 프롬프트 2
class Milestone(BaseModel):
    name: str
    date: Date | None


class MeetingStage(BaseModel):
    name: str
    purpose: str
    priority: Literal["must", "optional"]

    _lower_priority = field_validator("priority", mode="before")(_lower)


class AssignmentAnalysis(BaseModel):
    final_deadline: Date | None
    milestones: list[Milestone]
    deliverable_type: Literal["presentation", "report", "development", "기타"]
    meeting_stages: list[MeetingStage]

    _lower_type = field_validator("deliverable_type", mode="before")(_lower)


# 프롬프트 3
class Recommendation(BaseModel):
    candidate_id: str
    reason: str


class RecommendationReasons(BaseModel):
    recommendations: list[Recommendation]
