"""DB 종류(SQLite·PostgreSQL)와 상관없이 같아야 하는 동작.

평소에는 메모리 SQLite로 돌고, PostgreSQL로 확인할 때는
TEST_DATABASE_URL=postgresql://user:pass@localhost/teamplus_test python -m pytest
"""

from datetime import timedelta

import pytest

from app.ai.schemas import AssignmentAnalysis, MeetingStage, Milestone
from app.db import engine, init_db, normalize_url
from app.timeutil import today_kst
from tests.conftest import needs_ai_prompts, signup


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("postgresql://u:p@host/db", "postgresql+psycopg://u:p@host/db"),
        ("postgres://u:p@host/db", "postgresql+psycopg://u:p@host/db"),
        (
            "postgresql://u:p@/db?host=/cloudsql/proj:asia-northeast3:inst",
            "postgresql+psycopg://u:p@/db?host=/cloudsql/proj:asia-northeast3:inst",
        ),
        ("postgresql+psycopg://u:p@host/db", "postgresql+psycopg://u:p@host/db"),
        ("sqlite:///./teamplus.db", "sqlite:///./teamplus.db"),
    ],
)
def test_normalize_url(url, expected):
    assert normalize_url(url) == expected


def test_init_db_twice_is_safe():
    # 서버를 다시 띄워도(이미 테이블이 있어도) 문제없어야 한다
    init_db()
    init_db()


def test_timestamps_are_kst(client):
    h = signup(client)
    g = client.post("/api/groups", json={"name": "t"}, headers=h).json()
    me = client.get("/api/auth/me", headers=h).json()
    assert g["updatedAt"].endswith("+09:00")
    assert me["createdAt"].endswith("+09:00")


def test_invite_long_email_local_part(client):
    # 초대된 팀원의 표시 이름(이메일 앞부분)이 이름 칸(50자)을 넘어도 저장돼야 한다
    h = signup(client)
    g = client.post("/api/groups", json={"name": "t"}, headers=h).json()
    email = "a" * 60 + "@example.com"
    r = client.post(f"/api/groups/{g['id']}/invites", json={"email": email}, headers=h)
    assert r.status_code == 201, r.text
    assert r.json()["name"] == "a" * 50


@needs_ai_prompts
def test_long_ai_stage_text_is_saved(client, fake_llm):
    # AI가 만든 단계 이름·목적·중간 일정 이름은 길이 제한이 없다
    h = signup(client)
    g = client.post("/api/groups", json={"name": "t"}, headers=h).json()
    today = today_kst()
    long_name, long_purpose, long_milestone = "가" * 150, "나" * 400, "중간발표 " + "다" * 150
    fake_llm.set(
        AssignmentAnalysis,
        AssignmentAnalysis(
            final_deadline=today + timedelta(days=30),
            milestones=[Milestone(name=long_milestone, date=today + timedelta(days=15))],
            deliverable_type="presentation",
            meeting_stages=[
                MeetingStage(name=long_name, purpose=long_purpose, priority="must"),
                MeetingStage(name="중간발표 준비", purpose="점검", priority="must"),
            ],
        ),
    )
    r = client.post(f"/api/groups/{g['id']}/assignments", json={"noticeText": "공지"}, headers=h)
    assert r.status_code == 201, r.text
    stages = client.get(f"/api/groups/{g['id']}/assignments/{r.json()['id']}", headers=h).json()[
        "stages"
    ]
    assert stages[0]["name"] == long_name and stages[0]["purpose"] == long_purpose
    assert any(s["anchoredTo"] == long_milestone for s in stages)


def test_engine_matches_test_database():
    # TEST_DATABASE_URL로 PostgreSQL을 지정하면 실제로 PostgreSQL에 붙어 있어야 한다
    import os

    wanted = os.environ.get("TEST_DATABASE_URL", "sqlite://")
    assert engine.dialect.name == ("postgresql" if wanted.startswith("postgres") else "sqlite")
