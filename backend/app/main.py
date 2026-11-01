from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db import init_db
from app.routers import (
    assignments,
    availability,
    groups,
    places,
    recommendations,
    reservations,
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
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

for r in (groups, availability, places, reservations, recommendations, assignments):
    app.include_router(r.router, prefix="/api")


@app.get("/api/health", tags=["상태"])
def health():
    return {"status": "ok"}
