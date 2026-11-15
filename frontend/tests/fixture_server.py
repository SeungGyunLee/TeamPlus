"""Loopback verification server. Uses the real API and an isolated SQLite DB."""

import os
import sys
from datetime import timedelta
from pathlib import Path

backend = Path(__file__).resolve().parents[2] / "backend"
sys.path.insert(0, str(backend))
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["ANTHROPIC_API_KEY"] = ""
os.environ["RESERVATION_PROVIDER"] = "mock"

from app.ai.schemas import (
    AssignmentAnalysis,
    ParsedConditions,
    RecommendationReasons,
)
from app.deps import get_llm
from app.main import app
from app.timeutil import today_kst
from tests.fakes import FakeLLM


def conditions(_system: str, user: str):
    question = (
        "몇 명이 사용할 예정인가요?"
        if "[확인 질문]" in user and "답변:" not in user
        else None
    )
    return ParsedConditions(
        capacity=None if question else 3,
        noise_level="quiet",
        needs_outlet=True,
        needs_laptop_space=None,
        room_type="study_room",
        time_preference=None,
        clarifying_question=question,
    )


def analysis(_system: str, _user: str):
    today = today_kst()
    return AssignmentAnalysis(
        final_deadline=today + timedelta(days=12),
        milestones=[{"name": "중간 점검", "date": today + timedelta(days=6)}],
        deliverable_type="presentation",
        meeting_stages=[
            {"name": "주제 정하기", "purpose": "시연 범위 합의", "priority": "must"},
            {"name": "중간 점검", "purpose": "진행 상황 공유", "priority": "must"},
            {"name": "발표 연습", "purpose": "시연 순서 확인", "priority": "optional"},
        ],
    )


if os.environ.get("TEAMPLUS_TEST_AI") == "1":
    llm = FakeLLM()
    llm.set(ParsedConditions, conditions)
    llm.set(AssignmentAnalysis, analysis)
    llm.set(RecommendationReasons, RecommendationReasons(recommendations=[]))
    app.dependency_overrides[get_llm] = lambda: llm
