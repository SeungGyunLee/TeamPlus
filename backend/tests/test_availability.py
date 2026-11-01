"""공통 공강 계산 단위 테스트 (제안서 성공 기준 3). 프론트 tests/domain.test.ts와 같은 규칙."""

from datetime import date

from app.services.availability import MemberSchedule, color_for, weekly_blocks
from app.timetable import busy_blocks


def member(mid: str, *keys: str) -> MemberSchedule:
    return MemberSchedule(mid, mid, busy_blocks(list(keys)), tuple(keys))


def test_thirty_blocks_mon_to_fri_six_periods():
    blocks = weekly_blocks([member("a")])
    assert len(blocks) == 30
    assert {b.key for b in blocks} == {f"{d}-{p}" for d in range(5) for p in range(6)}


def test_ranked_by_count_then_day_then_period():
    # 프론트 rankedAvailability: 참석 인원 내림차순, 동률은 요일·교시순
    members = [member("a", "0-0", "1-1"), member("b", "0-0"), member("c")]
    blocks = weekly_blocks(members)
    assert blocks[0].key == "0-1"  # 전원 가능 중 월요일 2교시가 가장 앞
    assert [b.count for b in blocks] == sorted((b.count for b in blocks), reverse=True)
    assert blocks[-1].key == "0-0"  # 1명만 가능
    full = [b for b in blocks if b.count == 3]
    assert [(b.day, b.period) for b in full] == sorted((b.day, b.period) for b in full)


def test_member_lists_and_levels():
    members = [member("a", "2-3"), member("b", "2-3"), member("c")]
    by_key = {b.key: b for b in weekly_blocks(members)}
    b = by_key["2-3"]
    assert [m.member_id for m in b.available] == ["c"]
    assert [m.member_id for m in b.unavailable] == ["a", "b"]
    assert (b.count, b.total, b.level) == (1, 3, "partial")
    assert by_key["0-0"].level == "full"


def test_everyone_busy_is_none_level():
    by_key = {b.key: b for b in weekly_blocks([member("a", "4-5"), member("b", "4-5")])}
    assert by_key["4-5"].level == "none"


def test_busy_period_maps_to_real_time():
    # 수요일 3교시(12:00~13:30) 수업 → 12시 1시간 슬롯은 불가, 13:30부터 가능
    m = member("a", "2-2")
    wed = date(2026, 11, 4)
    assert not m.is_free(wed, 12 * 60, 13 * 60)
    assert not m.is_free(wed, 13 * 60, 14 * 60)  # 13:00~14:00은 13:30까지 겹침
    assert m.is_free(wed, 14 * 60, 15 * 60)
    assert m.is_free(date(2026, 11, 5), 12 * 60, 13 * 60)  # 목요일은 수업 없음


def test_color_rules_for_recommendation():
    assert color_for(4, 4, 1) == "green"
    assert color_for(3, 4, 1) == "orange"
    assert color_for(2, 4, 1) == "red"
    assert color_for(0, 4, 1) == "red"
