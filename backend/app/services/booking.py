"""예약 가능 기간·지난 시간 기준.

실제 예약은 중앙도서관 앱에서 하고, 이 서비스는 추천·현황 조회만 한다.
도서관 예약은 오늘부터 7일 안에서만 할 수 있어서 추천·호실 현황도 같은 기간만 다룬다.
"""

from datetime import date, datetime, timedelta

from app.timetable import BOOKING_DAYS

MSG_WINDOW = f"오늘부터 {BOOKING_DAYS}일 이내의 날짜만 볼 수 있어요."


def is_past(day: date, hour: int, now: datetime) -> bool:
    """프론트와 같은 기준: 오늘이면 현재 '시'보다 같거나 이른 슬롯은 지난 시간"""
    return day < now.date() or (day == now.date() and hour <= now.hour)


def booking_window(now: datetime) -> tuple[date, date]:
    """예약할 수 있는 첫날·마지막 날 (오늘 ~ 오늘+6일)"""
    today = now.date()
    return today, today + timedelta(days=BOOKING_DAYS - 1)


def clamp_to_window(date_from: date, date_to: date, now: datetime) -> tuple[date, date] | None:
    """요청 기간을 예약 가능 기간 안으로 자른다. 겹치는 날이 없으면 None.

    과제 회의 단계의 권장 기간처럼 지난 날짜나 7일 뒤까지 걸친 기간도 받아서
    예약할 수 있는 날만 추천하기 위함.
    """
    first, last = booking_window(now)
    lo, hi = max(date_from, first), min(date_to, last)
    return (lo, hi) if lo <= hi else None
