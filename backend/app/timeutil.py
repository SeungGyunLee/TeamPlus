"""시간 관련 공통 함수. 서비스 기준 시간대는 항상 한국 시간(KST)."""

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")
WEEKDAY_KO = ["월", "화", "수", "목", "금", "토", "일"]


def now_kst() -> datetime:
    return datetime.now(KST)


def today_kst() -> date:
    # 서버가 UTC로 돌아도 한국 날짜 기준으로 계산되도록 KST를 명시한다.
    return now_kst().date()


def to_minutes(t: time) -> int:
    return t.hour * 60 + t.minute


def from_minutes(m: int) -> time:
    if m >= 24 * 60:
        return time(23, 59)
    return time(m // 60, m % 60)


def date_range(start: date, end: date):
    """start부터 end까지(양끝 포함) 날짜를 하나씩 돌려준다."""
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


def format_slot(d: date, start: time, end: time) -> str:
    """예: 11/4(수) 16:00~18:00"""
    return f"{d.month}/{d.day}({WEEKDAY_KO[d.weekday()]}) {start:%H:%M}~{end:%H:%M}"
