"""호실이 차 있는 시간 = 시연용 점유 또는 실제 집현전 예약 현황.

프론트 isOccupied()와 같은 개념이다. (이 서비스 자체 예약 기능은 없음. 실제 예약은 도서관 앱에서)
"""

from collections.abc import Sequence
from datetime import date, time

from app.places.catalog import Room
from app.places.provider import Booked, ReservationProvider
from app.timeutil import to_minutes


def booked_map(
    provider: ReservationProvider, rooms: Sequence[Room], day: date
) -> dict[str, Booked]:
    return provider.get_booked(rooms, day)


def hour_taken(booked: Sequence[tuple[time, time]], hour: int) -> bool:
    start, end = hour * 60, (hour + 1) * 60
    return any(to_minutes(b0) < end and start < to_minutes(b1) for b0, b1 in booked)
