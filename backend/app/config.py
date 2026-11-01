"""환경 설정. 값은 환경변수나 backend/.env 파일에서 읽는다 (.env.example 참고)."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    # DB: 기본은 SQLite 파일. PostgreSQL로 바꿀 땐 URL만 교체하면 된다.
    database_url: str = f"sqlite:///{BACKEND_DIR / 'teamplus.db'}"

    # Claude API (키는 절대 코드에 쓰지 말고 .env에만)
    anthropic_api_key: str | None = None
    llm_model: str = "claude-haiku-5-5"
    llm_timeout_seconds: float = 30.0
    # 프롬프트 원문은 AI 담당 파일에서 읽는다 (백엔드에 복사본 없음)
    ai_prompts_file: Path = BACKEND_DIR.parent / "ai" / "test_prompts.py"

    # 집현전 예약 현황 조회: mock | jiphyeonjeon
    reservation_provider: str = "mock"
    places_file: Path = BACKEND_DIR / "data" / "places.json"

    # 추천에서 이 인원 수까지 빠지면 '주황', 그보다 많이 빠지면 제외
    max_missing_members: int = 1

    # Expo 웹 미리보기(8081)에서 호출할 때 필요. Android 앱 자체는 CORS와 무관하다.
    cors_origins: list[str] = ["http://localhost:8081", "http://localhost:19006"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
