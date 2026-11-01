"""받은 Claude API 키로 프롬프트 3개가 실제로 동작하는지 확인하는 스크립트.

사용법 (backend 폴더에서):
    python scripts/smoke_llm.py          # 3개 모두
    python scripts/smoke_llm.py 1        # 프롬프트 1만 (2, 3도 가능)

backend/.env의 ANTHROPIC_API_KEY를 사용한다. 실제 API를 호출하므로 비용이 조금 든다.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.ai import service  # noqa: E402
from app.ai.client import AnthropicLLM  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.timeutil import today_kst  # noqa: E402

CONDITION_INPUTS = [
    "조용한 곳, 4명, 콘센트 있는 데",
    "집현전",
    "목요일 저녁에 노트북 쓸 수 있는 스터디룸 5명",
]

NOTICE = """[팀 프로젝트 안내]
주제: 지역 문제 해결 서비스 기획 발표
중간발표: 11월 20일 (기획안 5분 발표)
최종발표: 12월 7일 (15분 발표 + 질의응답)
"""

CANDIDATES = [
    {
        "candidate_id": "C01",
        "place_name": "집현전 101호",
        "date": "2026-11-04",
        "start": "16:00",
        "end": "18:00",
        "score": 100,
        "status": "green",
        "conditions_met": [
            "11/4(수) 16:00~18:00 전원 참석 가능",
            "최대 4명 수용(필요 4명)",
            "콘센트 있음",
        ],
        "conflicts": [],
    },
    {
        "candidate_id": "C02",
        "place_name": "집현전 102호",
        "date": "2026-11-04",
        "start": "16:00",
        "end": "18:00",
        "score": 85,
        "status": "orange",
        "conditions_met": ["11/4(수) 16:00~18:00 3/4명 참석 가능", "콘센트 있음"],
        "conflicts": ["철수 시간표와 겹침(1명 조정 필요)"],
    },
]


def show(title: str, obj) -> None:
    print(f"\n=== {title}")
    data = obj.model_dump(mode="json") if hasattr(obj, "model_dump") else obj
    print(json.dumps(data, ensure_ascii=False, indent=2))


def main() -> None:
    settings = get_settings()
    if not settings.anthropic_api_key:
        sys.exit("backend/.env에 ANTHROPIC_API_KEY를 넣어주세요.")
    llm = AnthropicLLM(settings.anthropic_api_key, settings.llm_model, settings.llm_timeout_seconds)
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    print(f"model={settings.llm_model}")

    if which in ("1", "all"):
        for text in CONDITION_INPUTS:
            show(f"프롬프트 1: {text}", service.parse_conditions(llm, text))
    if which in ("2", "all"):
        show("프롬프트 2: 과제 공지", service.analyze_assignment(llm, NOTICE, today_kst()))
    if which in ("3", "all"):
        reasons, source = service.explain_candidates(llm, CANDIDATES)
        show(f"프롬프트 3 (source={source})", reasons)


if __name__ == "__main__":
    main()
