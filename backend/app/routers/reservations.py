"""집현전 가상 예약 (프론트 예약·내 예약 화면). 규칙은 app/services/booking.py."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_catalog, get_provider
from app.models import Group, Reservation
from app.occupancy import booked_map, hour_taken
from app.places.catalog import Catalog
from app.places.provider import ReservationProvider
from app.schemas import ReservationCreate, ReservationOut
from app.services.booking import MSG_OCCUPIED, BookingError, validate_booking
from app.timeutil import now_kst

router = APIRouter(prefix="/reservations", tags=["예약"])


@router.post("", response_model=ReservationOut, status_code=201, summary="가상 예약 만들기")
def create_reservation(
    body: ReservationCreate,
    catalog: Catalog = Depends(get_catalog),
    provider: ReservationProvider = Depends(get_provider),
    db: Session = Depends(get_db),
):
    room = catalog.room(body.room_id)
    group = db.get(Group, body.group_id)
    occupied = group_conflict = False
    if room is not None and group is not None:
        try:
            occupied = hour_taken(
                booked_map(db, provider, [room], body.date).get(room.id, []), body.hour
            )
        except NotImplementedError as e:
            raise HTTPException(503, str(e)) from e
        group_conflict = (
            db.scalar(
                select(Reservation.id).where(
                    Reservation.group_id == group.id,
                    Reservation.date == body.date,
                    Reservation.hour == body.hour,
                    Reservation.status == "active",
                )
            )
            is not None
        )
    try:
        validate_booking(
            room_capacity=room.capacity if room else None,
            group_exists=group is not None,
            member_count=len(group.members) if group else 0,
            day=body.date,
            hour=body.hour,
            now=now_kst(),
            occupied=occupied,
            group_conflict=group_conflict,
        )
    except BookingError as e:
        raise HTTPException(400, str(e)) from e

    reservation = Reservation(
        group_id=group.id,
        group_name=group.name,
        room_id=room.id,
        date=body.date,
        hour=body.hour,
    )
    db.add(reservation)
    try:
        db.commit()
    except IntegrityError as e:
        # 동시에 같은 슬롯을 예약한 경우 DB 고유 제약이 막는다.
        db.rollback()
        raise HTTPException(409, MSG_OCCUPIED) from e
    db.refresh(reservation)
    return reservation


@router.get("", response_model=list[ReservationOut], summary="예약 내역 (최근 순)")
def list_reservations(
    group_id: str | None = Query(default=None, alias="groupId"),
    status: str | None = Query(default=None, pattern="^(active|cancelled)$"),
    db: Session = Depends(get_db),
):
    q = select(Reservation).order_by(Reservation.created_at.desc())
    if group_id:
        q = q.where(Reservation.group_id == group_id)
    if status:
        q = q.where(Reservation.status == status)
    return db.scalars(q).all()


@router.post("/{reservation_id}/cancel", response_model=ReservationOut, summary="예약 취소")
def cancel_reservation(reservation_id: str, db: Session = Depends(get_db)):
    r = db.get(Reservation, reservation_id)
    if r is None:
        raise HTTPException(404, "예약을 찾을 수 없어요.")
    r.status = "cancelled"
    db.commit()
    db.refresh(r)
    return r
