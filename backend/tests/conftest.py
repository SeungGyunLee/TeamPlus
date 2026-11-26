import os

# 앱을 import하기 전에 테스트 환경을 고정한다 (실제 DB 파일·API 키를 쓰지 않음).
# PostgreSQL로 돌려볼 때: TEST_DATABASE_URL=postgresql://user:pass@localhost/teamplus_test
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL", "sqlite://")
os.environ["ANTHROPIC_API_KEY"] = ""
os.environ["RESERVATION_PROVIDER"] = "mock"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import deps, models  # noqa: E402, F401
from app.config import get_settings  # noqa: E402
from app.db import Base, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.places.provider import StaticReservationProvider  # noqa: E402
from app.services import auth as auth_service  # noqa: E402
from app.services.mail import MemoryMailer  # noqa: E402
from tests.fakes import FakeLLM  # noqa: E402

# 테스트 속도를 위해 비밀번호 해시 비용을 낮춘다 (실제 서버는 2^15)
auth_service.SCRYPT_N = 2**10


def signup(client, email="me@example.com", nickname="나", password="password123") -> dict:
    """가입하고 Authorization 헤더를 돌려준다."""
    r = client.post(
        "/api/auth/signup", json={"email": email, "password": password, "nickname": nickname}
    )
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['accessToken']}"}


# 팀원의 ai/test_prompts.py가 있어야 하는 테스트 (AI 브랜치 머지 전에는 건너뜀)
AI_PROMPTS_PRESENT = get_settings().ai_prompts_file.exists()
needs_ai_prompts = pytest.mark.skipif(
    not AI_PROMPTS_PRESENT, reason="ai/test_prompts.py가 없어요 (AI 브랜치 머지 전)"
)


@pytest.fixture(autouse=True)
def _fresh_db():
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture
def fake_llm() -> FakeLLM:
    return FakeLLM()


@pytest.fixture
def provider() -> StaticReservationProvider:
    return StaticReservationProvider()


@pytest.fixture
def mailer() -> MemoryMailer:
    """보낸 메일을 모아두는 가짜 메일 발송기 (실제로 보내지 않음)"""
    return MemoryMailer()


@pytest.fixture
def client(fake_llm, provider, mailer):
    app.dependency_overrides[deps.get_llm] = lambda: fake_llm
    app.dependency_overrides[deps.get_provider] = lambda: provider
    app.dependency_overrides[deps.get_mailer] = lambda: mailer
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
