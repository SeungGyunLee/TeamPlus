"""시간 관련 공통 함수. 서비스 기준 시간대는 항상 한국 시간(KST)."""

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")
WEEKDAY_KO = ["월", "화", "수", "목", "금", "토", "일"]


def now_kst() -> datetime:
    return datetime.now(KST)


def as_kst(dt: datetime) -> datetime:
    """DB에서 읽은 시각을 KST로 맞춘다.

    SQLite는 시간대를 빼고 돌려준다 (저장한 시각은 모두 KST라서 KST를 붙인다).
    PostgreSQL은 UTC 시각으로 돌려준다 (KST로 바꾼다).
    """
    return dt.astimezone(KST) if dt.tzinfo else dt.replace(tzinfo=KST)


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
