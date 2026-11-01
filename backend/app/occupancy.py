"""호실이 차 있는 시간 = 시연용 점유(또는 실제 집현전) + 이 서비스에서 만든 활성 예약.

프론트 isOccupied()와 같은 개념이다.
"""

from collections.abc import Sequence
from datetime import date, time

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Reservation
from app.places.catalog import Room
from app.places.provider import Booked, ReservationProvider
from app.timeutil import to_minutes


def booked_map(
    db: Session, provider: ReservationProvider, rooms: Sequence[Room], day: date
) -> dict[str, Booked]:
    result = provider.get_booked(rooms, day)
    rows = db.scalars(
        select(Reservation).where(
            Reservation.date == day,
            Reservation.status == "active",
            Reservation.room_id.in_([r.id for r in rooms]),
        )
    )
    for r in rows:
        result.setdefault(r.room_id, []).append((time(r.hour), time(r.hour + 1)))
    return result


def hour_taken(booked: Sequence[tuple[time, time]], hour: int) -> bool:
    start, end = hour * 60, (hour + 1) * 60
    return any(to_minutes(b0) < end and start < to_minutes(b1) for b0, b1 in booked)
