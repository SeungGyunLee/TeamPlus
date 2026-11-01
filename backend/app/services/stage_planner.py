"""회의 단계 날짜 배치.

핸드오프: AI는 날짜를 계산하지 않고, 각 단계가 어느 기간에 들어갈지는 코드가 계산한다.

입력: 프롬프트 2가 뽑은 meeting_stages(순서대로), milestones, 최종 마감일
출력: 단계마다 회의를 잡을 날짜 구간 [window_start, window_end]

규칙
1. 회의는 마감 전날까지 잡는다 (마감 당일은 제출·발표).
2. 남은 날짜보다 단계가 많으면 optional 단계를 뒤에서부터 뺀다.
3. 중간발표 같은 milestone과 관련된 단계는 그 날짜 직전 ANCHOR_SPAN_DAYS일 안에 고정한다.
4. 마지막 단계(리허설 등)는 마감 직전 ANCHOR_SPAN_DAYS일 안에 둔다.
5. 나머지 단계는 사이의 기간을 순서대로 고르게 나눠 갖는다.
날짜가 모자라면 구간이 하루로 줄어들거나 겹칠 수 있다.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal

ANCHOR_SPAN_DAYS = 3

DeadlineStatus = Literal["ok", "missing", "past"]


class PlanningError(ValueError):
    pass


@dataclass(frozen=True)
class StageSpec:
    name: str
    purpose: str
    priority: Literal["must", "optional"]


@dataclass(frozen=True)
class MilestoneSpec:
    name: str
    date: date | None


@dataclass
class PlannedStage:
    position: int
    name: str
    purpose: str
    priority: str
    window_start: date | None = None
    window_end: date | None = None
    anchored_to: str | None = None
    dropped: bool = False


def deadline_status(final_deadline: date | None, today: date) -> DeadlineStatus:
    if final_deadline is None:
        return "missing"
    if final_deadline <= today:
        return "past"
    return "ok"


def _norm(s: str) -> str:
    return re.sub(r"\s+", "", s)


def is_related(stage_name: str, milestone_name: str) -> bool:
    """단계 이름과 milestone 이름이 같은 일정을 가리키는지 (예: '중간점검' ↔ '중간발표')."""
    a, b = _norm(stage_name), _norm(milestone_name)
    if not a or not b:
        return False
    if b in a or a in b:
        return True
    return len(b) >= 2 and b[:2] in a


def _split(run: list[PlannedStage], lo: date, hi: date, fallback: date) -> None:
    if not run:
        return
    if hi < lo:
        for p in run:
            p.window_start = p.window_end = fallback
        return
    total = (hi - lo).days + 1
    k = len(run)
    for i, p in enumerate(run):
        s = i * total // k
        e = max(s, (i + 1) * total // k - 1)
        p.window_start = lo + timedelta(days=s)
        p.window_end = lo + timedelta(days=e)


def plan_stages(
    stages: Sequence[StageSpec],
    milestones: Sequence[MilestoneSpec],
    today: date,
    final_deadline: date | None,
) -> list[PlannedStage]:
    status = deadline_status(final_deadline, today)
    if status == "missing":
        raise PlanningError("최종 마감일이 없어 회의 일정을 배치할 수 없어요.")
    if status == "past":
        raise PlanningError("최종 마감일이 오늘이거나 이미 지났어요.")
    assert final_deadline is not None

    last_day = final_deadline - timedelta(days=1)
    total_days = (last_day - today).days + 1
    span = timedelta(days=ANCHOR_SPAN_DAYS - 1)

    planned = [PlannedStage(i, s.name, s.purpose, s.priority) for i, s in enumerate(stages)]

    # 2) 날짜가 모자라면 optional부터 뒤에서 제외
    active = list(planned)
    for p in reversed(planned):
        if len(active) <= total_days:
            break
        if p.priority == "optional":
            p.dropped = True
            active.remove(p)

    # 3) milestone에 묶기 (순서가 뒤집히는 묶음은 무시)
    anchors: dict[int, date] = {}
    used: set[int] = set()
    prev_end = today - timedelta(days=1)
    for idx, p in enumerate(active):
        for mi, m in enumerate(milestones):
            if mi in used or m.date is None or not (today < m.date <= final_deadline):
                continue
            if not is_related(p.name, m.name):
                continue
            end = min(m.date - timedelta(days=1), last_day)
            if end < prev_end:
                continue
            anchors[idx] = end
            p.anchored_to = m.name
            used.add(mi)
            prev_end = end
            break

    # 4·5) 구간 나누기
    left = today
    run: list[PlannedStage] = []
    for idx, p in enumerate(active):
        if idx not in anchors:
            run.append(p)
            continue
        end = anchors[idx]
        # 앞 단계들이 하루씩은 가질 수 있게 하되, 고정 단계는 최대 span일
        start = max(end - span, min(left + timedelta(days=len(run)), end))
        start = max(start, min(left, end))
        _split(run, left, start - timedelta(days=1), fallback=min(left, end))
        p.window_start, p.window_end = start, end
        left = end + timedelta(days=1)
        run = []

    if run:
        # 마지막 단계는 마감 직전에 고정하되, 앞 단계들이 하루씩은 가질 수 있게 한다.
        last = run.pop()
        start = max(last_day - span, min(left + timedelta(days=len(run)), last_day))
        start = max(start, min(left, last_day))
        last.window_start, last.window_end = start, last_day
        _split(run, left, start - timedelta(days=1), fallback=min(left, last_day))

    return planned
