# TeamPlus 백엔드 이미지
#
# 백엔드가 AI 담당의 ai/test_prompts.py를 읽기 때문에 저장소 최상위(TeamPlus/)에서 빌드한다.
#   cd TeamPlus
#   docker build -f backend/Dockerfile -t teamplus-backend .
# 무엇을 이미지에 넣을지는 backend/Dockerfile.dockerignore가 정한다 (backend/와 ai/만, .env는 제외).
#
# 이미지 안 폴더 구조는 저장소와 같다:
#   /app/backend/app/...    ← 서버 코드
#   /app/ai/test_prompts.py ← 프롬프트 원문 (config.ai_prompts_file 기본 경로와 일치)

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    # SQLite 파일은 컨테이너 밖(볼륨)에 둔다. PostgreSQL을 쓰면 실행할 때 DATABASE_URL만 바꾼다.
    DATABASE_URL=sqlite:////data/teamplus.db \
    PORT=8000

WORKDIR /app/backend

# 의존성 먼저 설치 (코드만 바뀌면 이 층은 캐시를 재사용해서 빌드가 빠르다)
COPY backend/requirements.txt .
RUN pip install -r requirements.txt

COPY ai/ /app/ai/
COPY backend/ /app/backend/

# root가 아닌 사용자로 실행
RUN useradd --create-home --uid 10001 app \
    && mkdir -p /data \
    && chown app:app /data
USER app
VOLUME ["/data"]

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\", \"8000\")}/api/health', timeout=3)"

# 호스팅 서비스(Render·Railway·Cloud Run 등)가 PORT 환경변수를 주면 그 포트로 뜬다.
# --proxy-headers: HTTPS를 앞단 프록시가 처리할 때 원래 주소·프로토콜을 알 수 있게 한다.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]
