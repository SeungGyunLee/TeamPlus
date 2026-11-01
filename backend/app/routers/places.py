"""장소 목록·상세, 집현전 호실과 날짜별 예약 가능 시간 (프론트 장소·예약 화면)."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_catalog, get_provider
from app.models import Group, Reservation
from app.occupancy import booked_map, hour_taken
from app.places.catalog import Catalog, Place
from app.places.provider import ReservationProvider
from app.schemas import RoomAvailabilityOut, RoomOut, SlotOut, SlotState
from app.services.booking import is_past
from app.timetable import HOURS, hour_label
from app.timeutil import now_kst

router = APIRouter(tags=["장소·호실"])


@router.get("/places", response_model=list[Place], summary="장소 목록")
def list_places(catalog: Catalog = Depends(get_catalog)):
    return list(catalog.places)


@router.get("/places/{place_id}", response_model=Place, summary="장소 상세")
def read_place(place_id: str, catalog: Catalog = Depends(get_catalog)):
    place = catalog.place(place_id)
    if place is None:
        raise HTTPException(404, "공간을 찾을 수 없어요.")
    return place


@router.get("/rooms", response_model=list[RoomOut], summary="집현전 호실 목록")
def list_rooms(catalog: Catalog = Depends(get_catalog)):
    return list(catalog.rooms)


@router.get(
    "/rooms/availability",
    response_model=list[RoomAvailabilityOut],
    summary="날짜별 호실 시간 상태 (예약 화면의 시간 선택 목록)",
)
def rooms_availability(
    day: date = Query(alias="date"),
    group_id: str | None = Query(default=None, alias="groupId"),
    catalog: Catalog = Depends(get_catalog),
    provider: ReservationProvider = Depends(get_provider),
    db: Session = Depends(get_db),
):
    group = db.get(Group, group_id) if group_id else None
    if group_id and group is None:
        raise HTTPException(404, "모임을 찾을 수 없어요.")
    rooms = list(catalog.rooms)
    try:
        booked = booked_map(db, provider, rooms, day)
    except NotImplementedError as e:
        raise HTTPException(503, str(e)) from e

    group_rows = (
        list(
            db.scalars(
                select(Reservation).where(
                    Reservation.group_id == group.id,
                    Reservation.date == day,
                    Reservation.status == "active",
                )
            )
        )
        if group
        else []
    )
    mine = {(r.room_id, r.hour) for r in group_rows}
    group_hours = {r.hour for r in group_rows}
    now = now_kst()

    result = []
    for room in rooms:
        fits = None if group is None else len(group.members) <= room.capacity
        slots = []
        for h in HOURS:
            state: SlotState
            if is_past(day, h, now):
                state = "past"
            elif (room.id, h) in mine:
                state = "mine"
            elif hour_taken(booked.get(room.id, []), h):
                state = "occupied"
            elif h in group_hours:
                state = "group_conflict"
            else:
                state = "available"
            slots.append(
                SlotOut(
                    hour=h,
                    label=hour_label(h),
                    state=state,
                    selectable=state == "available" and fits is not False,
                )
            )
        result.append(
            RoomAvailabilityOut(
                room_id=room.id,
                room_name=room.full_name,
                capacity=room.capacity,
                fits_group=fits,
                slots=slots,
            )
        )
    return result
