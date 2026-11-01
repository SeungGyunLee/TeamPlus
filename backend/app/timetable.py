"""프론트(frontend/src/domain/model.ts)와 같은 시간 규칙.

- 시간표: 월~금 × 6교시. 교시는 09:00부터 90분씩 (마지막 16:30~18:00).
  블록 키는 "요일-교시" 문자열. 예: "0-0" = 월요일 1교시, "1-2" = 화요일 3교시.
- 예약: 시간표와 별개로 1시간 단위. 시작 시각 09~18시 (마지막 18:00~19:00).
- 예약 가능 기간: 오늘부터 30일.
"""

import re
from datetime import time

from app.services.availability import BusyBlock

DAYS = ["월", "화", "수", "목", "금"]
PERIOD_COUNT = 6
PERIOD_MINUTES = 90
FIRST_PERIOD_START = 9 * 60

# 예약 시작 시각 (9시 ~ 18시)
HOURS = list(range(9, 19))
BOOKING_DAYS = 30

# 새 모임을 만들 때 기본으로 들어가는 팀원 (프론트 NEW_GROUP_MEMBER_NAMES)
DEFAULT_MEMBER_NAMES = ["짱구", "철수", "훈이"]

SLOT_KEY_RE = re.compile(r"^[0-4]-[0-5]$")


def slot_key(day: int, period: int) -> str:
    return f"{day}-{period}"


def parse_slot_key(key: str) -> tuple[int, int]:
    if not SLOT_KEY_RE.match(key):
        raise ValueError(f"잘못된 시간표 키: {key} (예: '0-2' = 월요일 3교시)")
    day, period = key.split("-")
    return int(day), int(period)


def period_range(period: int) -> tuple[time, time]:
    """교시 → (시작, 끝). 0교시 인덱스 = 1교시 09:00~10:30"""
    start = FIRST_PERIOD_START + period * PERIOD_MINUTES
    end = start + PERIOD_MINUTES
    return time(start // 60, start % 60), time(end // 60, end % 60)


def period_label(period: int) -> str:
    """프론트 PERIODS와 같은 표기. 예: 09:00–10:30"""
    s, e = period_range(period)
    return f"{s:%H:%M}–{e:%H:%M}"


def busy_blocks(keys: list[str]) -> tuple[BusyBlock, ...]:
    """시간표 키 목록 → 계산용 바쁜 시간 블록"""
    blocks = []
    for key in keys:
        day, period = parse_slot_key(key)
        start, end = period_range(period)
        blocks.append(BusyBlock(day, start, end))
    return tuple(blocks)


def hour_label(hour: int) -> str:
    """프론트 hourLabel과 같은 표기. 예: 16:00–17:00"""
    return f"{hour:02d}:00–{hour + 1:02d}:00"
