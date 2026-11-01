"""프론트(frontend/src/domain)와 규칙이 같은지 확인하는 테스트."""

from datetime import date, datetime, time

import pytest

from app.config import get_settings
from app.places.catalog import load_catalog
from app.places.provider import seed_occupied
from app.services.booking import (
    MSG_CAPACITY,
    MSG_GROUP_CONFLICT,
    MSG_INVALID,
    MSG_OCCUPIED,
    MSG_RANGE,
    BookingError,
    validate_booking,
)
from app.timetable import HOURS, busy_blocks, hour_label, period_label, period_range

# 프론트 isSeedOccupied()를 node로 직접 돌려서 얻은 값
FRONTEND_SEED = {
    ("J201", "2026-11-04"): [9, 11, 16, 18],
    ("J202", "2026-11-10"): [11, 13, 18],
    ("J301", "2026-12-01"): [9, 11, 16, 18],
    ("J302", "2026-11-20"): [12, 14],
}


@pytest.mark.parametrize(("key", "expected"), FRONTEND_SEED.items())
def test_seed_occupancy_matches_frontend(key, expected):
    room, day = key
    assert [h for h in HOURS if seed_occupied(room, day, h)] == expected
    assert [h for h in HOURS if seed_occupied(room, date.fromisoformat(day), h)] == expected


def test_timetable_constants_match_frontend():
    # 프론트 PERIODS
    assert [period_label(p) for p in range(6)] == [
        "09:00–10:30",
        "10:30–12:00",
        "12:00–13:30",
        "13:30–15:00",
        "15:00–16:30",
        "16:30–18:00",
    ]
    assert HOURS == list(range(9, 19))  # 프론트 HOURS
    assert hour_label(18) == "18:00–19:00"
    assert period_range(5) == (time(16, 30), time(18, 0))
    assert busy_blocks(["0-0"])[0].weekday == 0
    with pytest.raises(ValueError):
        busy_blocks(["5-0"])  # 토요일 없음
    with pytest.raises(ValueError):
        busy_blocks(["0-6"])  # 7교시 없음


def test_catalog_matches_frontend_seed():
    catalog = load_catalog(get_settings().places_file)
    assert [p.id for p in catalog.places] == ["jiphyeon", "reading", "cafe"]
    assert [(r.id, r.name, r.capacity) for r in catalog.rooms] == [
        ("J201", "201호", 4),
        ("J202", "202호", 4),
        ("J301", "301호", 6),
        ("J302", "302호", 8),
    ]
    assert catalog.room("J301").full_name == "집현전 301호"


NOW = datetime(2026, 11, 2, 14, 30)


def check(**kw):
    base = dict(
        room_capacity=4,
        group_exists=True,
        member_count=3,
        day=date(2026, 11, 3),
        hour=10,
        now=NOW,
        occupied=False,
        group_conflict=False,
    )
    base.update(kw)
    validate_booking(**base)


def test_valid_booking_passes():
    check()


@pytest.mark.parametrize(
    ("kw", "message"),
    [
        ({"room_capacity": None}, MSG_INVALID),
        ({"group_exists": False}, MSG_INVALID),
        ({"hour": 19}, MSG_INVALID),
        ({"hour": 8}, MSG_INVALID),
        ({"day": date(2026, 11, 1)}, MSG_RANGE),  # 어제
        ({"day": date(2026, 12, 2)}, MSG_RANGE),  # 오늘+30일 (범위는 +29일까지)
        ({"day": date(2026, 11, 2), "hour": 14}, MSG_RANGE),  # 오늘 현재 시각과 같은 시
        ({"member_count": 5}, MSG_CAPACITY),
        ({"occupied": True}, MSG_OCCUPIED),
        ({"group_conflict": True}, MSG_GROUP_CONFLICT),
    ],
)
def test_booking_rules_and_messages(kw, message):
    with pytest.raises(BookingError, match=message):
        check(**kw)


def test_booking_boundaries():
    check(day=date(2026, 12, 1))  # 오늘+29일은 가능
    check(day=date(2026, 11, 2), hour=15)  # 오늘이라도 다음 시는 가능
    check(member_count=4)  # 정원과 같으면 가능
