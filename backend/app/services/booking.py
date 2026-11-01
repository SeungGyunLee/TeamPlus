"""가상 예약 검증 규칙. 프론트 src/domain/booking.ts의 book()과 같은 순서·같은 오류 문구.

1. 호실·모임이 있고, 시간이 09~18시 중 하나이고, 날짜가 올바른지
2. 오늘부터 30일 안이고, 오늘이면 이미 지난 시간이 아닌지
3. 모임 인원이 호실 정원을 넘지 않는지
4. 그 시간이 이미 차 있지 않은지 (시연용 점유 + 다른 예약)
5. 같은 모임이 같은 시간에 다른 예약을 갖고 있지 않은지
"""

from datetime import date, datetime, timedelta

from app.timetable import BOOKING_DAYS, HOURS

MSG_INVALID = "예약 정보를 다시 확인해 주세요."
MSG_RANGE = "현재 이후 30일 이내의 시간을 선택해 주세요."
MSG_CAPACITY = "팀 인원보다 큰 인실을 선택해 주세요."
MSG_OCCUPIED = "이미 예약된 시간입니다. 다른 시간을 선택해 주세요."
MSG_GROUP_CONFLICT = "이 모임은 같은 시간에 다른 예약이 있어요."


class BookingError(ValueError):
    pass


def is_past(day: date, hour: int, now: datetime) -> bool:
    """프론트와 같은 기준: 오늘이면 현재 '시'보다 같거나 이른 슬롯은 지난 시간"""
    return day < now.date() or (day == now.date() and hour <= now.hour)


def booking_window(now: datetime) -> tuple[date, date]:
    today = now.date()
    return today, today + timedelta(days=BOOKING_DAYS - 1)


def validate_booking(
    *,
    room_capacity: int | None,
    group_exists: bool,
    member_count: int,
    day: date,
    hour: int,
    now: datetime,
    occupied: bool,
    group_conflict: bool,
) -> None:
    if room_capacity is None or not group_exists or hour not in HOURS:
        raise BookingError(MSG_INVALID)
    first, last = booking_window(now)
    if day < first or day > last or is_past(day, hour, now):
        raise BookingError(MSG_RANGE)
    if member_count > room_capacity:
        raise BookingError(MSG_CAPACITY)
    if occupied:
        raise BookingError(MSG_OCCUPIED)
    if group_conflict:
        raise BookingError(MSG_GROUP_CONFLICT)
