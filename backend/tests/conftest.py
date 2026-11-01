import os

# 앱을 import하기 전에 테스트 환경을 고정한다 (실제 DB 파일·API 키를 쓰지 않음).
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["ANTHROPIC_API_KEY"] = ""
os.environ["RESERVATION_PROVIDER"] = "mock"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import deps, models  # noqa: E402, F401
from app.config import get_settings  # noqa: E402
from app.db import Base, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.places.provider import StaticReservationProvider  # noqa: E402
from tests.fakes import FakeLLM  # noqa: E402

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
def client(fake_llm, provider):
    app.dependency_overrides[deps.get_llm] = lambda: fake_llm
    app.dependency_overrides[deps.get_provider] = lambda: provider
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
