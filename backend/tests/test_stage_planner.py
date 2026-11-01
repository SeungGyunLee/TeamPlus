from datetime import date, timedelta

import pytest

from app.services.stage_planner import (
    MilestoneSpec,
    PlanningError,
    StageSpec,
    deadline_status,
    is_related,
    plan_stages,
)

TODAY = date(2026, 11, 2)
PRESENTATION = [
    StageSpec("주제 확정", "발표 주제와 역할을 정한다", "must"),
    StageSpec("자료조사 공유", "조사한 자료를 공유한다", "must"),
    StageSpec("중간점검", "중간발표 준비 상태를 점검한다", "must"),
    StageSpec("리허설", "최종 발표 리허설", "must"),
]


def test_milestone_anchoring_and_rehearsal_near_deadline():
    plan = plan_stages(
        PRESENTATION, [MilestoneSpec("중간발표", date(2026, 11, 20))], TODAY, date(2026, 12, 7)
    )
    by_name = {p.name: p for p in plan}

    mid = by_name["중간점검"]
    assert mid.anchored_to == "중간발표"
    assert (mid.window_start, mid.window_end) == (date(2026, 11, 17), date(2026, 11, 19))

    assert (by_name["리허설"].window_start, by_name["리허설"].window_end) == (
        date(2026, 12, 4),
        date(2026, 12, 6),
    )
    assert by_name["주제 확정"].window_start == TODAY
    assert by_name["자료조사 공유"].window_end == date(2026, 11, 16)


def test_windows_are_ordered_and_inside_range():
    deadline = date(2026, 12, 7)
    plan = plan_stages(
        PRESENTATION, [MilestoneSpec("중간발표", date(2026, 11, 20))], TODAY, deadline
    )
    prev_end = TODAY - timedelta(days=1)
    for p in plan:
        assert TODAY <= p.window_start <= p.window_end < deadline
        assert p.window_start > prev_end  # 겹치지 않고 순서대로
        prev_end = p.window_end


def test_short_period_drops_optional_and_keeps_order():
    stages = [
        StageSpec("주제 확정", "", "must"),
        StageSpec("자료 공유", "", "optional"),
        StageSpec("중간 점검", "", "must"),
        StageSpec("리허설", "", "must"),
    ]
    plan = plan_stages(stages, [], TODAY, date(2026, 11, 5))  # 회의 가능일 3일
    assert [p.dropped for p in plan] == [False, True, False, False]
    active = [p for p in plan if not p.dropped]
    assert [(p.window_start, p.window_end) for p in active] == [
        (date(2026, 11, 2), date(2026, 11, 2)),
        (date(2026, 11, 3), date(2026, 11, 3)),
        (date(2026, 11, 4), date(2026, 11, 4)),
    ]
    assert plan[1].window_start is None


def test_very_short_period_still_gives_every_stage_a_day():
    plan = plan_stages(PRESENTATION, [], TODAY, TODAY + timedelta(days=2))  # 회의 가능일 2일
    assert all(p.window_start is not None for p in plan)
    assert all(TODAY <= p.window_end <= TODAY + timedelta(days=1) for p in plan)


def test_milestone_without_date_or_out_of_range_is_not_anchored():
    plan = plan_stages(
        PRESENTATION,
        [MilestoneSpec("중간발표", None), MilestoneSpec("중간검사", date(2026, 10, 1))],
        TODAY,
        date(2026, 12, 7),
    )
    assert all(p.anchored_to is None for p in plan)


def test_missing_or_past_deadline_raises():
    with pytest.raises(PlanningError):
        plan_stages(PRESENTATION, [], TODAY, None)
    with pytest.raises(PlanningError):
        plan_stages(PRESENTATION, [], TODAY, TODAY)
    assert deadline_status(None, TODAY) == "missing"
    assert deadline_status(TODAY, TODAY) == "past"
    assert deadline_status(TODAY + timedelta(days=1), TODAY) == "ok"


def test_is_related():
    assert is_related("중간점검", "중간발표")
    assert is_related("중간발표 준비", "중간발표")
    assert not is_related("리허설", "중간발표")
    assert not is_related("주제 확정", "")
