"""후보 점수화 단위 테스트 (제안서 성공 기준 3)."""

from datetime import date, datetime, time

from app.places.catalog import Room
from app.places.provider import StaticReservationProvider
from app.services.availability import BusyBlock, MemberSchedule
from app.services.scoring import (
    SearchConditions,
    candidate_payload,
    evaluate_window,
    recommend,
)
from app.services.time_preference import TimeFilter

WED = date(2026, 11, 4)


def place(
    pid="P1", cap=4, outlet=True, noise="quiet", laptop=True, room="study_room", reservable=True
):
    return Room(
        id=pid,
        place_id="jiphyeon",
        name=pid,
        full_name=f"집현전 {pid}",
        room_type=room,
        capacity=cap,
        has_outlet=outlet,
        noise_level=noise,
        laptop_space=laptop,
        reservable=reservable,
    )


def team(busy_names: dict[str, tuple[time, time]] | None = None, size=4):
    names = ["짱구", "철수", "훈이", "맹구"][:size]
    busy_names = busy_names or {}
    return [
        MemberSchedule(
            f"m{i}",
            n,
            (BusyBlock(WED.weekday(), *busy_names[n]),) if n in busy_names else (),
        )
        for i, n in enumerate(names, start=1)
    ]


def run(members, places, provider=None, cond=SearchConditions(), **kw):
    provider = provider or StaticReservationProvider()
    params = dict(
        duration_minutes=60,
        slot_minutes=30,
        day_start=time(16),
        day_end=time(18),
        max_missing=1,
        limit=5,
    )
    params.update(kw)
    return recommend(members, places, provider.get_booked, cond, WED, WED, **params)


# ---------- 상태 분류 ----------
def test_booked_window_is_always_red():
    # 제안서: 예약 마감 장소는 반드시 빨강
    ev = evaluate_window(
        place(), WED, 16 * 60, 17 * 60, team(), [(time(16), time(17))], SearchConditions(), 1
    )
    assert ev.status == "red"
    assert ev.exclude_reason == "booked"


def test_partially_booked_window_is_red():
    ev = evaluate_window(
        place(),
        WED,
        16 * 60,
        17 * 60,
        team(),
        [(time(16, 30), time(17, 30))],
        SearchConditions(),
        1,
    )
    assert ev.status == "red"


def test_booking_right_after_window_does_not_block():
    ev = evaluate_window(
        place(), WED, 16 * 60, 17 * 60, team(), [(time(17), time(18))], SearchConditions(), 1
    )
    assert ev.status == "green"


def test_all_available_and_conditions_met_is_green_100():
    cond = SearchConditions(needs_outlet=True, noise_level="quiet")
    ev = evaluate_window(place(), WED, 16 * 60, 17 * 60, team(), [], cond, 1)
    assert ev.status == "green"
    assert ev.score == 100
    assert ev.conflicts == []
    assert "콘센트 있음" in ev.conditions_met
    assert "조용한 공간" in ev.conditions_met
    assert ev.conditions_met[0] == "11/4(수) 16:00~17:00 전원 참석 가능"


def test_one_member_conflict_is_orange_and_named():
    members = team({"훈이": (time(16), time(17))})
    ev = evaluate_window(place(), WED, 16 * 60, 17 * 60, members, [], SearchConditions(), 1)
    assert ev.status == "orange"
    assert ev.conflicts == ["훈이 시간표와 겹침(1명 조정 필요)"]
    assert ev.score == 85  # 60*3/4 + 40
    assert "3/4명 참석 가능" in ev.conditions_met[0]


def test_unmet_soft_condition_is_orange():
    ev = evaluate_window(
        place(outlet=False),
        WED,
        16 * 60,
        17 * 60,
        team(),
        [],
        SearchConditions(needs_outlet=True),
        1,
    )
    assert ev.status == "orange"
    assert "콘센트 없음" in ev.conflicts
    assert ev.score == 60


def test_too_many_members_missing_is_red():
    members = team({"훈이": (time(16), time(17)), "맹구": (time(16), time(17))})
    ev = evaluate_window(place(), WED, 16 * 60, 17 * 60, members, [], SearchConditions(), 1)
    assert ev.status == "red"
    assert ev.exclude_reason == "not_enough_members"


def test_non_reservable_place_ignores_bookings():
    ev = evaluate_window(
        place(room="reading_room", reservable=False),
        WED,
        16 * 60,
        17 * 60,
        team(),
        [(time(16), time(17))],
        SearchConditions(),
        1,
    )
    assert ev.status == "green"
    assert "예약 없이 이용하는 공간" in ev.conditions_met


# ---------- 장소 단위 제외 ----------
def test_capacity_too_small_excludes_place():
    result = run(
        team(), [place("SMALL", cap=4), place("BIG", cap=6)], cond=SearchConditions(capacity=6)
    )
    assert [e.room.id for e in result.excluded_rooms] == ["SMALL"]
    assert "수용 인원 부족(최대 4명, 필요 6명)" in result.excluded_rooms[0].reasons
    assert all(c.evaluation.room.id == "BIG" for c in result.candidates)


def test_team_size_used_when_capacity_not_given():
    result = run(team(size=4), [place("TINY", cap=2)])
    assert result.candidates == []
    assert result.excluded_rooms[0].room.id == "TINY"


def test_room_type_mismatch_excludes_place():
    result = run(
        team(), [place("R", room="reading_room")], cond=SearchConditions(room_type="study_room")
    )
    assert result.candidates == []
    assert result.excluded_rooms[0].reasons[0].startswith("원하는 공간 종류가 아님")


# ---------- 후보 생성 ----------
def test_booked_windows_are_excluded_and_counted():
    provider = StaticReservationProvider()
    provider.add("P1", WED, time(16), time(17))
    result = run(team(), [place("P1")], provider)
    # 60분 구간 16:00, 16:30, 17:00 중 앞의 둘은 예약과 겹침
    assert result.excluded_windows["booked"] == 2
    assert [(c.evaluation.start, c.evaluation.status) for c in result.candidates] == [
        (time(17), "green")
    ]


def test_higher_score_first_and_times_do_not_overlap():
    places = [place("NO-OUTLET", outlet=False), place("OUTLET", outlet=True)]
    result = run(team(), places, cond=SearchConditions(needs_outlet=True), day_end=time(19))
    first = result.candidates[0].evaluation
    assert first.room.id == "OUTLET" and first.status == "green"
    evs = [c.evaluation for c in result.candidates]
    for i, a in enumerate(evs):
        for b in evs[i + 1 :]:
            assert not (a.start_min < b.end_min and b.start_min < a.end_min)
    assert [c.candidate_id for c in result.candidates] == [
        f"C{i:02d}" for i in range(1, len(evs) + 1)
    ]


def test_long_meetings_are_spread_one_hour_apart():
    result = run(team(), [place()], duration_minutes=120, day_start=time(9), limit=3)
    starts = sorted(c.evaluation.start_min for c in result.candidates)
    assert len(starts) == 3
    assert all(b - a >= 60 for a, b in zip(starts, starts[1:], strict=False))


def test_best_fit_room_preferred_on_tie():
    result = run(team(), [place("BIG", cap=8), place("FIT", cap=4)])
    assert result.candidates[0].evaluation.room.id == "FIT"


def test_time_filter_limits_windows():
    cond = SearchConditions(time_filter=TimeFilter(start_min=17 * 60))
    result = run(team(), [place()], cond=cond, day_end=time(19))
    assert result.candidates
    assert all(c.evaluation.start_min >= 17 * 60 for c in result.candidates)


def test_past_windows_are_skipped():
    result = run(team(), [place()], not_before=datetime(2026, 11, 4, 16, 45), day_end=time(19))
    assert all(c.evaluation.start_min >= 17 * 60 for c in result.candidates)


def test_limit_is_respected():
    result = run(team(), [place()], day_start=time(9), day_end=time(22), limit=3)
    assert len(result.candidates) == 3


def test_candidate_payload_contains_handoff_fields_and_time():
    result = run(team(), [place()])
    payload = candidate_payload(result.candidates[0])
    for key in ("candidate_id", "place_name", "score", "status", "conditions_met", "conflicts"):
        assert key in payload
    assert payload["date"] == "2026-11-04"
    assert payload["start"] == "16:00" and payload["end"] == "17:00"


def test_team_size_wins_when_user_says_fewer_people():
    # 프론트 예약 규칙: 팀 인원이 정원보다 많으면 예약 불가
    result = run(team(size=4), [place("SMALL", cap=3)], cond=SearchConditions(capacity=2))
    assert result.candidates == []
    assert "수용 인원 부족(최대 3명, 필요 4명)" in result.excluded_rooms[0].reasons


def test_group_already_booked_hour_is_skipped():
    blocked = frozenset({(WED, 16 * 60)})
    result = run(team(), [place()], blocked=blocked, day_end=time(19))
    assert all(c.evaluation.start_min != 16 * 60 for c in result.candidates)
    assert result.excluded_windows["group_conflict"] >= 1


def test_current_hour_counts_as_past_like_frontend():
    # 16:00 정각이어도 16시 슬롯은 지난 시간 (프론트: hour <= now.getHours())
    result = run(team(), [place()], not_before=datetime(2026, 11, 4, 16, 0), day_end=time(19))
    assert all(c.evaluation.start_min >= 17 * 60 for c in result.candidates)
