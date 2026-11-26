from app.config import Settings


def test_secret_values_are_stripped(monkeypatch):
    # Secret Manager·파일로 넣은 값 끝의 줄바꿈 때문에 DB 연결·API 키가 깨지지 않아야 한다
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@/db?host=/cloudsql/p:r:i\n")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "  sk-test\r\n")
    s = Settings(_env_file=None)
    assert s.database_url == "postgresql://u:p@/db?host=/cloudsql/p:r:i"
    assert s.anthropic_api_key == "sk-test"
