import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db import init_db
from app.routers import (
    assignments,
    auth,
    availability,
    groups,
    places,
    recommendations,
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    s = get_settings()
    if os.environ.get("K_SERVICE") and s.database_url.startswith("sqlite"):
        # Cloud Run 컨테이너의 파일은 재시작·새 배포 때 사라진다
        logging.getLogger("app").warning(
            "Cloud Run에서 SQLite를 쓰고 있어요. 회원·모임이 재시작하면 사라집니다. "
            "DATABASE_URL을 Cloud SQL(PostgreSQL) 주소로 설정하세요."
        )
    if s.reservation_provider == "jiphyeonjeon" and not (
        s.jiphyeonjeon_status_url and s.jiphyeonjeon_map_url
    ):
        logging.getLogger("app").warning(
            "RESERVATION_PROVIDER=jiphyeonjeon인데 JIPHYEONJEON_*_URL이 비어 있어요. "
            "호실 현황·추천이 503으로 응답합니다."
        )
    yield


app = FastAPI(
    title="TeamPlus API",
    version="0.1.0",
    description="AI 기반 팀플 시간·장소 추천 서비스 백엔드",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

for r in (auth, groups, availability, places, recommendations, assignments):
    app.include_router(r.router, prefix="/api")
app.include_router(groups.invites_router, prefix="/api")


@app.get("/api/health", tags=["상태"])
def health():
    return {"status": "ok"}
