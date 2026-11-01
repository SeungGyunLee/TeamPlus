"""공통 가능 시간(공강) 계산 (핸드오프: '코드가 담당').

프론트 src/domain/availability.ts와 같은 규칙:
- 월~금 × 6교시 = 30칸. 칸마다 참석 가능 인원/전체 인원과 명단을 센다.
- 정렬: 참석 가능 인원 많은 순 → 요일순 → 교시순 (rankedAvailability)
- 표시 단계(level): 전원 가능 full / 일부 가능 partial / 아무도 안 됨 none

추천 계산에서는 같은 시간표를 실제 날짜·시각 구간으로 펼쳐서 쓴다 (MemberSchedule.is_free).
"""

from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from datetime import date, time
from typing import Literal

from app.timeutil import to_minutes

Level = Literal["full", "partial", "none"]
Color = Literal["green", "orange", "red"]


@dataclass(frozen=True)
class BusyBlock:
    weekday: int  # 0=월 ... 4=금
    start: time
    end: time


@dataclass(frozen=True)
class MemberSchedule:
    member_id: str
    name: str
    busy: tuple[BusyBlock, ...] = ()
    busy_keys: tuple[str, ...] = ()  # 프론트 형식 원본 ("0-0" 등)

    def is_free(self, day: date, start_min: int, end_min: int) -> bool:
        """[start_min, end_min) 구간에 겹치는 수업이 없으면 True. 끝 시각은 포함하지 않는다."""
        wd = day.weekday()
        for b in self.busy:
            if b.weekday == wd and to_minutes(b.start) < end_min and start_min < to_minutes(b.end):
                return False
        return True


@dataclass(frozen=True)
class WeeklyBlock:
    key: str  # "요일-교시"
    day: int
    period: int
    available: tuple[MemberSchedule, ...]
    unavailable: tuple[MemberSchedule, ...]

    @property
    def count(self) -> int:
        return len(self.available)

    @property
    def total(self) -> int:
        return len(self.available) + len(self.unavailable)

    @property
    def level(self) -> Level:
        # 프론트 공강 화면의 색 구분과 같다
        if self.count == self.total:
            return "full"
        return "partial" if self.count > 0 else "none"


def weekly_blocks(
    members: Sequence[MemberSchedule], days: int = 5, periods: int = 6
) -> list[WeeklyBlock]:
    """30칸 공강 계산. 프론트 rankedAvailability()와 같은 순서로 돌려준다."""
    blocks = []
    for period in range(periods):
        for day in range(days):
            key = f"{day}-{period}"
            available = tuple(m for m in members if key not in m.busy_keys)
            unavailable = tuple(m for m in members if key in m.busy_keys)
            blocks.append(WeeklyBlock(key, day, period, available, unavailable))
    blocks.sort(key=lambda b: (-b.count, b.day, b.period))
    return blocks


def color_for(available: int, total: int, max_missing: int) -> Color:
    """추천 후보용 단계. 전원 green / max_missing명 이하 빠짐 orange / 그 이상 red"""
    if total <= 0 or available <= 0:
        return "red"
    missing = total - available
    if missing == 0:
        return "green"
    if missing <= max_missing:
        return "orange"
    return "red"


def iter_windows(start_min: int, end_min: int, step: int, length: int) -> Iterator[tuple[int, int]]:
    """start_min부터 step 간격으로 길이 length인 구간을 만든다. end_min을 넘지 않는다."""
    s = start_min
    while s + length <= end_min:
        yield s, s + length
        s += step


def split_members(
    members: Sequence[MemberSchedule], day: date, start_min: int, end_min: int
) -> tuple[list[MemberSchedule], list[MemberSchedule]]:
    available, unavailable = [], []
    for m in members:
        (available if m.is_free(day, start_min, end_min) else unavailable).append(m)
    return available, unavailable
