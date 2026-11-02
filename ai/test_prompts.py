"""
팀플 시간·장소 추천 서비스 — AI 프롬프트 테스트 스크립트

사용법:
    export ANTHROPIC_API_KEY="본인의 API 키"
    python3 test_prompts.py 1        # 프롬프트 1(조건 구조화)만 테스트
    python3 test_prompts.py 2        # 프롬프트 2(회의 단계 추출)만 테스트
    python3 test_prompts.py 3        # 프롬프트 3(추천 이유 생성)만 테스트
    python3 test_prompts.py all      # 전부 테스트

API 키는 https://console.anthropic.com 에서 발급받아요 (가입 시 무료 크레딧 제공).
"""

import sys
import json
import os
from anthropic import Anthropic

client = Anthropic()  # ANTHROPIC_API_KEY 환경변수를 자동으로 읽음
MODEL = "claude-sonnet-5-5"  # 필요하면 다른 모델로 바꿔도 됨


def call(system_prompt: str, user_content: str) -> str:
    resp = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=system_prompt,
        messages=[{"role": "user", "content": user_content}],
    )
    for block in resp.content:
        if block.type == "text":
            return block.text
    return ""


def strip_code_fence(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1] if "\n" in t else t
        if t.endswith("```"):
            t = t[: -3]
        elif "```" in t:
            t = t.rsplit("```", 1)[0]
    return t.strip()


def try_parse_json(text: str):
    text = strip_code_fence(text)
    try:
        return json.loads(text), None
    except json.JSONDecodeError as e:
        return None, str(e)


# ── 프롬프트 1: 자연어 조건 구조화 ──────────────────────────────
PROMPT_1 = """당신은 대학 팀플 장소 추천 시스템의 조건 분석기입니다.
사용자의 요청을 읽고 아래 JSON 형식으로만 답하세요. 설명이나 다른 텍스트는 쓰지 마세요.

{
  "capacity": "필요 인원수(숫자), 없으면 null",
  "noise_level": "quiet | normal | 무관 중 하나",
  "needs_outlet": "true | false | null (언급 없으면 null)",
  "needs_laptop_space": "true | false | null",
  "room_type": "study_room | reading_room | 무관 중 하나 (집현전·스터디룸을 콜어 말했으면 study_room)",
  "time_preference": "언급된 시간대가 있으면 그대로, 없으면 null",
  "clarifying_question": "추천에 꼭 필요한 정보가 빠졌을 때만 한 문장, 아니면 null"
}

규칙:
- 사용자가 말하지 않은 조건은 추측해서 채우지 마세요. 모르면 null로 두세요.
- clarifying_question은 인원수나 방 종류가 전혀 없을 때만 사용하고, 최대 한 개만 만드세요."""

TEST_CASES_1 = [
    "조용한 곳, 4명, 콘센트 있는 데",
    "내일 오후에 놀 수 있는 고요한 곳",
    "집현전",
    "6명이서 노트북 펴고 작업할 공간, 콘센트 꼭 필요해",
    "아무 데나 상관없어",
]


# ── 프롬프트 2: 과제 공지 → 회의 단계 추출 ──────────────────────
PROMPT_2 = """당신은 팀 프로젝트 일정 분석기입니다.
과제 공지를 읽고 아래 JSON 형식으로만 답하세요.

{
  "final_deadline": "최종 제출·발표일, YYYY-MM-DD. 공지에 연도가 없으면 현재에서 가까운 미래로 추정",
  "milestones": [
    {"name": "중간발표 등 공지에 명시된 중간 일정", "date": "YYYY-MM-DD, 모르면 null"}
  ],
  "deliverable_type": "presentation | report | development | 기타 중 하나",
  "meeting_stages": [
    {"name": "회의 단계 이름 (예: 주제 확정)", "purpose": "한 줄 설명", "priority": "must | optional"}
  ]
}

규칙:
- meeting_stages는 deliverable_type에 맞게 정하세요. presentation이면 보통 주제확정 → 자료조사공유 → 중간점검 → 리허설 순서입니다.
- 공지에 언급된 중간발표·검사는 반드시 하나의 회의 단계로 만드세요.
- 날짜를 직접 계산하지 마세요. 각 단계가 "언제쯤 어느 기간에 들어가야 하는지"는 코드가 계산합니다.
- meeting_stages는 3~5개를 넘지 않게 하세요.

오늘 날짜: 2026-10-31"""

TEST_CASES_2 = [
    "11월 20일 최종 발표, 중간발표는 11월 6일입니다.",
    "12월 1일까지 보고서 제출. 중간보고 없음.",
    "기말 과제: 웹 서비스 개발 및 시연. 12월 15일 발표, 11월 10일 중간 점검 있음.",
]


# ── 프롬프트 3: 추천 이유 설명 생성 ──────────────────────────────
PROMPT_3 = """당신은 팀플 장소·시간 추천 이유를 설명하는 도우미입니다.
아래 <candidates>는 이미 점수와 상태가 계산된 후보입니다.

규칙:
1. 각 후보마다 주어진 score·status를 바꿔 쓰지 마세요. 직접 계산하거나 다른 값으로 바꾸지 마세요.
2. 이유는 주어진 conditions_met·conflicts만 근거로 1~2문장으로 쓰세요. 후보에 없는 정보(가구, 창문 등)는 지어내지 마세요.
3. conflicts가 있으면 눈에 띄게 한 번에 언급하세요. (예: "B회의는 1명이 조정해야 해요")
4. 아래 JSON 형식으로만 답하세요.

{
  "recommendations": [
    {"candidate_id": "후보의 id", "reason": "설명 1~2문장"}
  ]
}

<candidates>
{candidates_json}
</candidates>"""

TEST_CASES_3 = [
    [
        {
            "candidate_id": "C01",
            "place_name": "집현전 101호",
            "score": 92,
            "status": "green",
            "conditions_met": ["4명 수용", "콘센트 있음", "11/4 16:00 전원 가능"],
            "conflicts": [],
        },
        {
            "candidate_id": "C02",
            "place_name": "집현전 102호",
            "score": 70,
            "status": "orange",
            "conditions_met": ["4명 수용", "콘센트 있음"],
            "conflicts": ["11/4 16:00에 1명 시간표 겹침"],
        },
    ]
]


def run_prompt_1():
    print("\n=== 프롬프트 1: 자연어 조건 구조화 ===")
    for case in TEST_CASES_1:
        out = call(PROMPT_1, f"사용자 요청: {case}")
        parsed, err = try_parse_json(out)
        print(f"\n입력: {case}")
        print(f"출력: {out}")
        if err:
            print(f"  ⚠ JSON 파싱 실패: {err}")


def run_prompt_2():
    print("\n=== 프롬프트 2: 과제 공지 → 회의 단계 추출 ===")
    for case in TEST_CASES_2:
        out = call(PROMPT_2, f"과제 공지: {case}")
        parsed, err = try_parse_json(out)
        print(f"\n입력: {case}")
        print(f"출력: {out}")
        if err:
            print(f"  ⚠ JSON 파싱 실패: {err}")
        elif parsed:
            stages = parsed.get("meeting_stages", [])
            print(f"  → 회의 단계 {len(stages)}개: {[s.get('name') for s in stages]}")


def run_prompt_3():
    print("\n=== 프롬프트 3: 추천 이유 설명 생성 ===")
    for candidates in TEST_CASES_3:
        prompt = PROMPT_3.replace("{candidates_json}", json.dumps(candidates, ensure_ascii=False, indent=2))
        out = call(prompt, "위 후보들에 대한 추천 이유를 작성하세요.")
        parsed, err = try_parse_json(out)
        print(f"\n입력 후보 수: {len(candidates)}")
        print(f"출력: {out}")
        if err:
            print(f"  ⚠ JSON 파싱 실패: {err}")
        elif parsed:
            for rec in parsed.get("recommendations", []):
                # score·status가 원본 그대로인지 확인 (AI가 바꿔치지 않았는지 체크)
                orig = next((c for c in candidates if c["candidate_id"] == rec["candidate_id"]), None)
                print(f"  → {rec['candidate_id']}: {rec['reason']}")


if __name__ == "__main__":
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY 환경변수가 설정되어 있지 않아요.")
        print('예: export ANTHROPIC_API_KEY="sk-ant-..."')
        sys.exit(1)

    target = sys.argv[1] if len(sys.argv) > 1 else "all"
    if target in ("1", "all"):
        run_prompt_1()
    if target in ("2", "all"):
        run_prompt_2()
    if target in ("3", "all"):
        run_prompt_3()
