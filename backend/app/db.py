from collections.abc import Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import get_settings


class Base(DeclarativeBase):
    pass


def normalize_url(url: str) -> str:
    """postgresql:// 처럼 드라이버를 안 적은 주소는 설치된 psycopg(3) 드라이버로 연결한다."""
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix) :]
    return url


def make_engine(url: str) -> Engine:
    url = normalize_url(url)
    if url.startswith("sqlite"):
        kwargs: dict = {"connect_args": {"check_same_thread": False}}
        if url in ("sqlite://", "sqlite:///:memory:"):
            # 메모리 DB는 연결마다 따로 생기므로 하나의 연결을 공유한다 (테스트용).
            kwargs["poolclass"] = StaticPool
        return create_engine(url, **kwargs)
    # PostgreSQL (Cloud SQL 등). 작은 인스턴스는 동시 연결 수가 적어서 풀을 작게 둔다.
    # pool_pre_ping: 오래 쉰 연결이 끊겨 있으면 새로 연결한다.
    return create_engine(url, pool_pre_ping=True, pool_size=5, max_overflow=5, pool_recycle=1800)


engine = make_engine(get_settings().database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


# 서버 여러 대가 동시에 처음 뜰 때 테이블을 한 번만 만들도록 잡는 잠금 번호 (아무 고정값)
_SCHEMA_LOCK_ID = 724_001


def init_db() -> None:
    """없는 테이블만 만든다. 이미 있는 테이블의 컬럼은 바꾸지 않는다."""
    from app import models  # noqa: F401  (테이블 등록)

    if engine.dialect.name == "postgresql":
        with engine.begin() as conn:
            conn.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": _SCHEMA_LOCK_ID})
            Base.metadata.create_all(conn)
    else:
        Base.metadata.create_all(engine)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
