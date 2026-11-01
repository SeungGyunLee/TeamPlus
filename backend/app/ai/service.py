"""AI 호출 지점 3곳. AI는 해석·설명만 하고, 계산·판단은 app/services의 코드가 한다.

프롬프트 원문은 백엔드에 두지 않고 AI 담당의 ai/test_prompts.py에서 PROMPT_1·2·3을 읽어 쓴다.
그 파일은 import하지 않는다 (파일 맨 위에서 Anthropic()을 만들어 키가 없으면 에러가 나기 때문).
대신 파일을 텍스트로 읽어 문자열 상수만 꺼낸다.
"""

import ast
import json
import re
from collections.abc import Sequence
from datetime import date
from functools import lru_cache
from pathlib import Path

from app.ai.client import LLMClient, LLMError
from app.ai.schemas import AssignmentAnalysis, ParsedConditions, RecommendationReasons
from app.config import get_settings

# user 메시지 형식 (ai/test_prompts.py에서 테스트한 형식 그대로)
CONDITIONS_USER_PREFIX = "사용자 요청: "
ASSIGNMENT_USER_PREFIX = "과제 공지: "
REASONS_USER_MESSAGE = "위 후보들에 대한 추천 이유를 작성하세요."

PROMPT_NAMES = ("PROMPT_1", "PROMPT_2", "PROMPT_3")


class PromptsUnavailable(LLMError):
    """ai/test_prompts.py가 없거나 PROMPT_1·2·3을 찾지 못함."""


@lru_cache
def load_prompts(path: str | None = None) -> dict[str, str]:
    """ai/test_prompts.py에서 PROMPT_1·2·3 문자열을 꺼낸다 (파일을 실행하지 않음)."""
    file = Path(path) if path else get_settings().ai_prompts_file
    if not file.exists():
        raise PromptsUnavailable(f"프롬프트 파일이 없어요: {file}")
    found = {}
    for node in ast.parse(file.read_text(encoding="utf-8")).body:
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id in PROMPT_NAMES
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            found[node.targets[0].id] = node.value.value
    missing = [n for n in PROMPT_NAMES if n not in found]
    if missing:
        raise PromptsUnavailable(f"{file}에서 {', '.join(missing)}를 찾지 못했어요")
    return found


def render_assignment_system(today: date) -> str:
    """프롬프트 2의 고정된 '오늘 날짜'를 호출 시점 KST 날짜로 바꾼다 (핸드오프 요구사항)."""
    prompt = load_prompts()["PROMPT_2"]
    return re.sub(r"오늘 날짜: \d{4}-\d{2}-\d{2}", f"오늘 날짜: {today.isoformat()}", prompt)


def render_reasons_system(candidates_json: str) -> str:
    # 프롬프트 안에 JSON 예시 중괄호가 있으므로 format() 대신 replace()
    return load_prompts()["PROMPT_3"].replace("{candidates_json}", candidates_json)


def parse_conditions(llm: LLMClient, text: str) -> ParsedConditions:
    """프롬프트 1: '조용한 곳, 4명, 콘센트' → 구조화된 조건"""
    return llm.parse(
        system=load_prompts()["PROMPT_1"],
        user=CONDITIONS_USER_PREFIX + text,
        output_type=ParsedConditions,
        max_tokens=1024,
    )


def analyze_assignment(llm: LLMClient, notice_text: str, today: date) -> AssignmentAnalysis:
    """프롬프트 2: 과제 공지 → 마감일·중간 일정·회의 단계. 오늘 날짜는 호출 시점 KST로 넣는다."""
    return llm.parse(
        system=render_assignment_system(today),
        user=ASSIGNMENT_USER_PREFIX + notice_text,
        output_type=AssignmentAnalysis,
        max_tokens=1024,
    )


def fallback_reason(candidate: dict) -> str:
    """AI 설명을 못 받았을 때 쓰는 기본 문구 (계산된 값만 사용)."""
    met = candidate.get("conditions_met") or []
    conflicts = candidate.get("conflicts") or []
    text = ", ".join(met)
    if conflicts:
        return f"{text}. 다만 {', '.join(conflicts)}."
    return f"{text}."


def explain_candidates(
    llm: LLMClient | None, candidates: Sequence[dict]
) -> tuple[dict[str, str], str]:
    """프롬프트 3: 후보별 추천 이유.

    반환: (candidate_id → 이유, 출처 'ai' | 'fallback' | 'partial')
    AI가 빠뜨리거나 실패한 후보(프롬프트 파일이 없는 경우 포함)는 기본 문구로 채운다.
    """
    if not candidates:
        return {}, "ai"
    fallback = {c["candidate_id"]: fallback_reason(c) for c in candidates}
    if llm is None:
        return fallback, "fallback"

    payload = json.dumps(list(candidates), ensure_ascii=False, indent=2)
    max_tokens = min(4096, 256 + 200 * len(candidates))
    try:
        out = llm.parse(
            system=render_reasons_system(payload),
            user=REASONS_USER_MESSAGE,
            output_type=RecommendationReasons,
            max_tokens=max_tokens,
        )
    except LLMError:
        return fallback, "fallback"

    reasons = {
        r.candidate_id: r.reason.strip()
        for r in out.recommendations
        if r.candidate_id in fallback and r.reason.strip()
    }
    source = "ai" if len(reasons) == len(fallback) else "partial"
    return {cid: reasons.get(cid, fb) for cid, fb in fallback.items()}, source
