"""추천 후보 생성·점수화 (핸드오프: '후보 점수·상태 산정은 코드가 담당').

후보 = (집현전 호실, 날짜, 1시간 슬롯) 조합. 프론트 예약 단위와 같다.

상태
- red (제외)   : 예약 마감이거나, 참석 가능 인원이 너무 적음. 프롬프트 3에는 넘기지 않는다.
- green (추천)  : 전원 참석 가능 + 사용자가 말한 조건 모두 충족
- orange (조건부): 1명 이상 시간 조정이 필요하거나, 일부 조건이 맞지 않음

호실 자체가 안 맞는 경우(정원 부족, 방 종류 불일치)는 시간대마다 따지지 않고
excluded_rooms로 한 번에 돌려준다. 정원은 '사용자가 말한 인원'과 '팀 인원' 중 큰 값 기준
(프론트 예약 규칙: 팀 인원이 정원보다 많으면 예약 불가).

점수 (0~100, 정렬용)
- 시간 일치  : TIME_WEIGHT × (참석 가능 인원 / 팀 인원)
- 조건 충족도: CONDITION_WEIGHT × (충족한 조건 수 / 사용자가 말한 조건 수), 말한 조건이 없으면 만점
"""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, time
from typing import Literal

from app.places.catalog import ROOM_TYPE_LABEL, Room
from app.services.availability import MemberSchedule, color_for, iter_windows, split_members
from app.services.time_preference import TimeFilter
from app.timeutil import date_range, format_slot, from_minutes, to_minutes

TIME_WEIGHT = 60
CONDITION_WEIGHT = 40

Status = Literal["green", "orange", "red"]
BookedMap = Mapping[str, Sequence[tuple[time, time]]]


@dataclass(frozen=True)
class SearchConditions:
    capacity: int | None = None
    noise_level: Literal["quiet", "normal"] | None = None
    needs_outlet: bool | None = None
    needs_laptop_space: bool | None = None
    room_type: Literal["study_room", "reading_room"] | None = None
    time_filter: TimeFilter | None = None


@dataclass
class WindowEvaluation:
    room: Room
    date: date
    start_min: int
    end_min: int
    status: Status
    score: int
    available: list[MemberSchedule]
    unavailable: list[MemberSchedule]
    conditions_met: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    exclude_reason: Literal["booked", "not_enough_members"] | None = None

    @property
    def start(self) -> time:
        return from_minutes(self.start_min)

    @property
    def end(self) -> time:
        return from_minutes(self.end_min)


@dataclass
class Candidate:
    candidate_id: str
    evaluation: WindowEvaluation


@dataclass
class ExcludedRoom:
    room: Room
    reasons: list[str]


@dataclass
class RecommendationResult:
    candidates: list[Candidate]
    excluded_rooms: list[ExcludedRoom]
    excluded_windows: dict[str, int]


def room_hard_failures(room: Room, cond: SearchConditions, team_size: int) -> list[str]:
    """장소 자체가 조건에 안 맞는 이유. 비어 있으면 통과."""
    reasons = []
    if cond.room_type and room.room_type != cond.room_type:
        reasons.append(f"원하는 공간 종류가 아님({ROOM_TYPE_LABEL[room.room_type]})")
    required = max(cond.capacity or 0, team_size)
    if room.capacity < required:
        reasons.append(f"수용 인원 부족(최대 {room.capacity}명, 필요 {required}명)")
    return reasons


def soft_conditions(room: Room, cond: SearchConditions) -> tuple[list[str], list[str]]:
    """사용자가 말한 선택 조건을 (충족, 미충족) 문장 목록으로 나눈다."""
    met: list[str] = []
    unmet: list[str] = []
    if cond.noise_level == "quiet":
        (met if room.noise_level == "quiet" else unmet).append(
            "조용한 공간" if room.noise_level == "quiet" else "조용한 공간은 아님"
        )
    if cond.needs_outlet:
        (met if room.has_outlet else unmet).append(
            "콘센트 있음" if room.has_outlet else "콘센트 없음"
        )
    if cond.needs_laptop_space:
        (met if room.laptop_space else unmet).append(
            "노트북 쓸 공간 있음" if room.laptop_space else "노트북 쓸 공간 부족"
        )
    return met, unmet


def _overlaps(start_min: int, end_min: int, booked: Sequence[tuple[time, time]]) -> bool:
    return any(to_minutes(b0) < end_min and start_min < to_minutes(b1) for b0, b1 in booked)


def evaluate_window(
    room: Room,
    day: date,
    start_min: int,
    end_min: int,
    members: Sequence[MemberSchedule],
    booked: Sequence[tuple[time, time]],
    cond: SearchConditions,
    max_missing: int,
) -> WindowEvaluation:
    team_size = len(members)
    available, unavailable = split_members(members, day, start_min, end_min)
    base = dict(
        room=room,
        date=day,
        start_min=start_min,
        end_min=end_min,
        available=available,
        unavailable=unavailable,
    )

    if room.reservable and _overlaps(start_min, end_min, booked):
        return WindowEvaluation(
            **base, status="red", score=0, conflicts=["예약 마감"], exclude_reason="booked"
        )
    if color_for(len(available), team_size, max_missing) == "red":
        return WindowEvaluation(
            **base,
            status="red",
            score=0,
            conflicts=[f"참석 가능 인원 부족({len(available)}/{team_size}명)"],
            exclude_reason="not_enough_members",
        )

    slot_text = format_slot(day, from_minutes(start_min), from_minutes(end_min))
    if not unavailable:
        conditions_met = [f"{slot_text} 전원 참석 가능"]
    else:
        conditions_met = [f"{slot_text} {len(available)}/{team_size}명 참석 가능"]
    required = max(cond.capacity or 0, team_size)
    conditions_met.append(f"최대 {room.capacity}명 수용(필요 {required}명)")
    if cond.room_type:
        conditions_met.append(ROOM_TYPE_LABEL[room.room_type])
    if not room.reservable:
        conditions_met.append("예약 없이 이용하는 공간")

    met, unmet = soft_conditions(room, cond)
    conditions_met += met

    conflicts: list[str] = []
    if unavailable:
        names = ", ".join(m.name for m in unavailable)
        conflicts.append(f"{names} 시간표와 겹침({len(unavailable)}명 조정 필요)")
    conflicts += unmet

    specified = len(met) + len(unmet)
    time_score = TIME_WEIGHT * len(available) / team_size
    cond_score = CONDITION_WEIGHT * (len(met) / specified if specified else 1)
    status: Status = "green" if not unavailable and not unmet else "orange"

    return WindowEvaluation(
        **base,
        status=status,
        score=round(time_score + cond_score),
        conditions_met=conditions_met,
        conflicts=conflicts,
    )


def recommend(
    members: Sequence[MemberSchedule],
    rooms: Sequence[Room],
    booked_for_day: Callable[[Sequence[Room], date], BookedMap],
    cond: SearchConditions,
    date_from: date,
    date_to: date,
    *,
    duration_minutes: int,
    slot_minutes: int,
    day_start: time,
    day_end: time,
    max_missing: int,
    limit: int = 5,
    not_before: datetime | None = None,
    blocked: frozenset[tuple[date, int]] = frozenset(),
) -> RecommendationResult:
    team_size = len(members)
    required = max(cond.capacity or 0, team_size)

    excluded_rooms: list[ExcludedRoom] = []
    eligible: list[Room] = []
    for p in rooms:
        reasons = room_hard_failures(p, cond, team_size)
        if reasons:
            excluded_rooms.append(ExcludedRoom(p, reasons))
        else:
            eligible.append(p)

    excluded_windows = {"booked": 0, "not_enough_members": 0, "group_conflict": 0}
    pool: list[WindowEvaluation] = []
    if team_size == 0 or not eligible:
        return RecommendationResult([], excluded_rooms, excluded_windows)

    for day in date_range(date_from, date_to):
        booked_map = booked_for_day(eligible, day)
        for room in eligible:
            lo = max(to_minutes(day_start), to_minutes(room.open_time))
            hi = min(to_minutes(day_end), to_minutes(room.close_time))
            for s, e in iter_windows(lo, hi, slot_minutes, duration_minutes):
                if not_before and (
                    day < not_before.date()
                    or (day == not_before.date() and s // 60 <= not_before.hour)
                ):
                    continue  # 이미 지난 시간 (프론트와 같은 기준)
                if (day, s) in blocked:
                    excluded_windows["group_conflict"] += 1
                    continue  # 이 모임이 그 시간에 이미 다른 예약을 가짐
                if cond.time_filter and not cond.time_filter.allows(day, s, e):
                    continue
                ev = evaluate_window(
                    room, day, s, e, members, booked_map.get(room.id, ()), cond, max_missing
                )
                if ev.status == "red":
                    excluded_windows[ev.exclude_reason] += 1
                else:
                    pool.append(ev)

    # 점수 높은 순 → 빠른 날짜·시간 → 인원에 딱 맞는 방 순
    pool.sort(
        key=lambda ev: (-ev.score, ev.date, ev.start_min, ev.room.capacity - required, ev.room.id)
    )

    # 비슷한 시간대만 몰리지 않게, 같은 날에는 시작 시각이 min_gap분 이상 떨어진 후보만 고른다.
    # (1시간 회의면 시간이 겹치지 않고, 2시간 회의면 1시간 간격으로 고른다)
    min_gap = min(duration_minutes, 60)
    chosen: list[WindowEvaluation] = []
    for ev in pool:
        if len(chosen) >= limit:
            break
        if any(c.date == ev.date and abs(c.start_min - ev.start_min) < min_gap for c in chosen):
            continue
        chosen.append(ev)

    candidates = [Candidate(f"C{i:02d}", ev) for i, ev in enumerate(chosen, start=1)]
    return RecommendationResult(candidates, excluded_rooms, excluded_windows)


def candidate_payload(c: Candidate) -> dict:
    """프롬프트 3에 넘길 후보 JSON (핸드오프 필드 + 시간 필드)."""
    ev = c.evaluation
    return {
        "candidate_id": c.candidate_id,
        "place_name": ev.room.full_name,
        "date": ev.date.isoformat(),
        "start": ev.start.strftime("%H:%M"),
        "end": ev.end.strftime("%H:%M"),
        "score": ev.score,
        "status": ev.status,
        "conditions_met": ev.conditions_met,
        "conflicts": ev.conflicts,
    }
