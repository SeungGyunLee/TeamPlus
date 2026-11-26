"""환경 설정. 값은 환경변수나 backend/.env 파일에서 읽는다 (.env.example 참고)."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        # 비밀값을 파일·Secret Manager로 넣을 때 끝에 붙는 줄바꿈·공백을 지운다
        str_strip_whitespace=True,
    )

    # DB: 기본은 SQLite 파일. PostgreSQL(Google Cloud SQL 등)은 URL만 바꾸면 된다.
    #   postgresql://사용자:비밀번호@호스트:5432/DB이름
    #   Cloud Run → Cloud SQL: postgresql://사용자:비밀번호@/DB이름?host=/cloudsql/프로젝트:지역:인스턴스
    database_url: str = f"sqlite:///{BACKEND_DIR / 'teamplus.db'}"

    # Claude API (키는 절대 코드에 쓰지 말고 .env에만)
    anthropic_api_key: str | None = None
    llm_model: str = "claude-haiku-5-5"
    llm_timeout_seconds: float = 30.0
    # 프롬프트 원문은 AI 담당 파일에서 읽는다 (백엔드에 복사본 없음)
    ai_prompts_file: Path = BACKEND_DIR.parent / "ai" / "test_prompts.py"

    # 집현전 예약 현황 조회: mock(시연용) | jiphyeonjeon(실제 조회)
    reservation_provider: str = "mock"
    # 학교 비공개 API, 사용 전 확인 필요. 주소는 저장소에 올리지 않고 .env에만 둔다.
    jiphyeonjeon_status_url: str | None = None
    jiphyeonjeon_map_url: str | None = None
    # 학교 서버 부담을 줄이기 위한 캐시 시간(초). 연동 안내 문서 권장 3~5분
    jiphyeonjeon_cache_seconds: int = 180
    jiphyeonjeon_timeout_seconds: float = 5.0
    places_file: Path = BACKEND_DIR / "data" / "places.json"

    # 로그인 토큰 유효 기간 (일)
    token_ttl_days: int = 30
    # 비밀번호 재설정 인증 코드 유효 시간 (분)
    password_reset_minutes: int = 10

    # 메일 발송: console(보내지 않고 서버 로그에 출력) | smtp(실제 발송)
    # SMTP 계정·비밀번호는 .env에만 둔다.
    mail_backend: str = "console"
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_security: str = "starttls"  # starttls(587) | ssl(465) | none
    mail_from: str | None = None  # 보내는 주소. 비우면 SMTP_USERNAME

    # 추천에서 이 인원 수까지 빠지면 '주황', 그보다 많이 빠지면 제외
    max_missing_members: int = 1

    # Expo 웹 미리보기(8081)에서 호출할 때 필요. Android 앱 자체는 CORS와 무관하다.
    cors_origins: list[str] = ["http://localhost:8081", "http://localhost:19006"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
