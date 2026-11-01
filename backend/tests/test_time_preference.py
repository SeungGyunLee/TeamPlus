from datetime import date

from app.services.time_preference import TimeFilter, parse_time_preference

TODAY = date(2026, 11, 1)  # 일요일


def p(text):
    return parse_time_preference(text, TODAY)


def test_weekday_and_period():
    f = p("목요일 저녁")
    assert f.weekdays == {3}
    assert (f.start_min, f.end_min) == (18 * 60, 22 * 60)


def test_after_hour_with_pm_prefix():
    f = p("오후 3시 이후")
    assert f.start_min == 15 * 60 and f.end_min is None


def test_bare_small_hour_means_pm_and_starts_near_it():
    f = p("3시")
    assert f.start_min == 15 * 60 and f.latest_start_min == 16 * 60


def test_hour_range():
    f = p("2시~5시")
    assert (f.start_min, f.end_min) == (14 * 60, 17 * 60)
    f = p("오전 10시부터 오후 1시까지")
    assert (f.start_min, f.end_min) == (10 * 60, 13 * 60)


def test_before_hour_and_half():
    f = p("6시 반 전")
    assert f.end_min == 18 * 60 + 30


def test_weekend_and_weekday_words():
    assert p("주말 오전").weekdays == {5, 6}
    assert p("평일").weekdays == {0, 1, 2, 3, 4}


def test_relative_and_explicit_dates():
    assert p("내일").dates == {date(2026, 11, 2)}
    f = p("11/4 오후")
    assert f.dates == {date(2026, 11, 4)}
    assert (f.start_min, f.end_min) == (12 * 60, 18 * 60)
    assert p("11월 5일").dates == {date(2026, 11, 5)}
    # 이미 지난 날짜는 내년으로 본다
    assert p("10/3").dates == {date(2027, 10, 3)}


def test_duration_is_not_a_time():
    assert p("2시간 정도") is None


def test_unrecognized_or_empty_returns_none():
    assert p("아무 때나") is None
    assert p("") is None
    assert p(None) is None


def test_filter_allows():
    f = TimeFilter(weekdays=frozenset({2}), start_min=16 * 60, end_min=20 * 60)
    wed, thu = date(2026, 11, 4), date(2026, 11, 5)
    assert f.allows(wed, 16 * 60, 18 * 60)
    assert not f.allows(wed, 15 * 60, 17 * 60)
    assert not f.allows(wed, 19 * 60, 21 * 60)
    assert not f.allows(thu, 16 * 60, 18 * 60)
