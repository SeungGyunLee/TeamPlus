"""AI 호출부 테스트. 실제 API는 부르지 않고 FakeLLM으로 입력·출력 처리만 검증한다."""

import json
from datetime import date

import pytest
from pydantic import TypeAdapter

from app.ai import service
from app.ai.client import LLMError
from app.ai.schemas import (
    AssignmentAnalysis,
    ParsedConditions,
    Recommendation,
    RecommendationReasons,
)
from app.ai.service import (
    PromptsUnavailable,
    load_prompts,
    render_assignment_system,
    render_reasons_system,
)
from tests.conftest import needs_ai_prompts
from tests.fakes import FakeLLM

CANDIDATES = [
    {
        "candidate_id": "C01",
        "place_name": "집현전 101호",
        "score": 100,
        "status": "green",
        "conditions_met": ["11/4(수) 16:00~18:00 전원 참석 가능", "콘센트 있음"],
        "conflicts": [],
    },
    {
        "candidate_id": "C02",
        "place_name": "집현전 102호",
        "score": 85,
        "status": "orange",
        "conditions_met": ["11/4(수) 16:00~18:00 3/4명 참석 가능"],
        "conflicts": ["훈이 시간표와 겹침(1명 조정 필요)"],
    },
]


FAKE_AI_FILE = '''
from anthropic import Anthropic
client = Anthropic()  # 실행되면 키가 없어서 에러 → 실행하지 않고 읽어야 함
raise SystemExit("이 파일은 실행되면 안 됨")
PROMPT_1 = """조건 분석기"""
PROMPT_2 = """일정 분석기
오늘 날짜: 2026-10-31"""
PROMPT_3 = """{"recommendations": []}
<candidates>
{candidates_json}
</candidates>"""
'''


def test_load_prompts_reads_strings_without_running_file(tmp_path):
    f = tmp_path / "test_prompts.py"
    f.write_text(FAKE_AI_FILE, encoding="utf-8")
    prompts = load_prompts(str(f))
    assert prompts["PROMPT_1"] == "조건 분석기"
    assert prompts["PROMPT_2"].endswith("오늘 날짜: 2026-10-31")


def test_load_prompts_missing_file_or_names(tmp_path):
    with pytest.raises(PromptsUnavailable):
        load_prompts(str(tmp_path / "없음.py"))
    f = tmp_path / "partial.py"
    f.write_text('PROMPT_1 = "x"\n', encoding="utf-8")
    with pytest.raises(PromptsUnavailable, match="PROMPT_2, PROMPT_3"):
        load_prompts(str(f))


@needs_ai_prompts
def test_team_prompts_keep_handoff_rules():
    prompts = load_prompts()
    assert "추측해서 채우지 마세요" in prompts["PROMPT_1"]
    assert "날짜를 직접 계산하지 마세요" in prompts["PROMPT_2"]
    assert "{candidates_json}" in prompts["PROMPT_3"]


@needs_ai_prompts
def test_assignment_prompt_gets_dynamic_date():
    text = render_assignment_system(date(2026, 11, 1))
    assert text.endswith("오늘 날짜: 2026-11-01")
    assert "2026-10-31" not in text and "{today}" not in text
    assert '"final_deadline"' in text  # JSON 예시 중괄호가 깨지지 않음


@needs_ai_prompts
def test_reasons_prompt_inserts_json_without_format_errors():
    payload = json.dumps(CANDIDATES, ensure_ascii=False)
    text = render_reasons_system(payload)
    assert payload in text
    assert "{candidates_json}" not in text
    assert '"recommendations"' in text


@needs_ai_prompts
def test_analyze_assignment_passes_today():
    llm = FakeLLM()
    llm.set(
        AssignmentAnalysis,
        AssignmentAnalysis(
            final_deadline=None, milestones=[], deliverable_type="report", meeting_stages=[]
        ),
    )
    service.analyze_assignment(llm, "공지", date(2026, 11, 1))
    assert llm.calls[0]["system"].endswith("오늘 날짜: 2026-11-01")
    assert llm.calls[0]["user"] == "과제 공지: 공지"


@needs_ai_prompts
def test_parse_conditions_uses_prompt_1():
    llm = FakeLLM()
    expected = ParsedConditions(
        capacity=4,
        noise_level="quiet",
        needs_outlet=True,
        needs_laptop_space=None,
        room_type="study_room",
        time_preference=None,
        clarifying_question=None,
    )
    llm.set(ParsedConditions, expected)
    assert service.parse_conditions(llm, "조용한 곳, 4명, 콘센트") == expected
    assert llm.calls[0]["user"] == "사용자 요청: 조용한 곳, 4명, 콘센트"
    assert llm.calls[0]["system"] == load_prompts()["PROMPT_1"]


@needs_ai_prompts
def test_explain_all_from_ai():
    llm = FakeLLM()
    llm.set(
        RecommendationReasons,
        RecommendationReasons(
            recommendations=[
                Recommendation(candidate_id="C01", reason="전원 가능해요."),
                Recommendation(candidate_id="C02", reason="1명이 조정해야 해요."),
            ]
        ),
    )
    reasons, source = service.explain_candidates(llm, CANDIDATES)
    assert source == "ai"
    assert reasons == {"C01": "전원 가능해요.", "C02": "1명이 조정해야 해요."}
    assert '"candidate_id": "C02"' in llm.calls[0]["system"]


@needs_ai_prompts
def test_explain_fills_missing_and_ignores_unknown_ids():
    llm = FakeLLM()
    llm.set(
        RecommendationReasons,
        RecommendationReasons(
            recommendations=[
                Recommendation(candidate_id="C01", reason="좋아요."),
                Recommendation(candidate_id="C99", reason="없는 후보"),
            ]
        ),
    )
    reasons, source = service.explain_candidates(llm, CANDIDATES)
    assert source == "partial"
    assert set(reasons) == {"C01", "C02"}
    assert "훈이 시간표와 겹침" in reasons["C02"]


def test_explain_falls_back_on_error_or_no_client():
    llm = FakeLLM()
    llm.error = LLMError("timeout")
    reasons, source = service.explain_candidates(llm, CANDIDATES)
    assert source == "fallback" and set(reasons) == {"C01", "C02"}

    reasons, source = service.explain_candidates(None, CANDIDATES)
    assert source == "fallback"
    assert reasons["C01"].startswith("11/4(수) 16:00~18:00 전원 참석 가능")


@pytest.mark.parametrize("model", [ParsedConditions, AssignmentAnalysis, RecommendationReasons])
def test_schemas_are_accepted_by_structured_outputs(model):
    """SDK가 스키마를 structured outputs 형식으로 바꿀 수 있는지 (API 호출 없음)."""
    transform = pytest.importorskip("anthropic.lib._parse._transform").transform_schema
    schema = transform(TypeAdapter(model).json_schema())
    assert schema["additionalProperties"] is False
