"""프론트(frontend/src/domain)와 규칙이 같은지 확인하는 테스트."""

from datetime import date, datetime, time

import pytest

from app.config import get_settings
from app.places.catalog import load_catalog
from app.places.provider import seed_occupied
from app.services.booking import booking_window, clamp_to_window, is_past
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


def test_catalog_has_real_jiphyeonjeon_rooms():
    # 실제 그룹학습실: 4인실 4~11실, 6인실 2·3·12실, 10인실 1·13실
    # (10·11실은 학교 API로 현황을 알 수 없어 제외)
    catalog = load_catalog(get_settings().places_file)
    assert [p.id for p in catalog.places] == ["jiphyeon", "reading", "cafe"]
    by_size = {}
    for r in catalog.rooms:
        by_size.setdefault(r.capacity, []).append(int(r.source_room_no))
    assert by_size == {10: [1, 13], 6: [2, 3, 12], 4: [4, 5, 6, 7, 8, 9]}
    assert catalog.room("J12").full_name == "집현전 12실"
    assert all(r.has_outlet and r.laptop_space and r.noise_level == "normal" for r in catalog.rooms)


NOW = datetime(2026, 11, 18, 14, 30)


def test_booking_window_is_seven_days():
    assert booking_window(NOW) == (date(2026, 11, 18), date(2026, 11, 24))


def test_past_hour_like_frontend():
    assert is_past(date(2026, 11, 18), 14, NOW)  # 지금 시와 같은 시는 지난 시간
    assert not is_past(date(2026, 11, 18), 15, NOW)
    assert is_past(date(2026, 11, 17), 18, NOW)


@pytest.mark.parametrize(
    ("given", "expected"),
    [
        ((date(2026, 11, 19), date(2026, 11, 20)), (date(2026, 11, 19), date(2026, 11, 20))),
        ((date(2026, 11, 10), date(2026, 11, 20)), (date(2026, 11, 18), date(2026, 11, 20))),
        ((date(2026, 11, 20), date(2026, 12, 31)), (date(2026, 11, 20), date(2026, 11, 24))),
        ((date(2026, 11, 1), date(2026, 11, 17)), None),
        ((date(2026, 11, 25), date(2026, 11, 30)), None),
    ],
)
def test_clamp_to_window(given, expected):
    assert clamp_to_window(*given, NOW) == expected
