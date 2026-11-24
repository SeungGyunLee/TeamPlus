"""장소 목록·상세, 집현전 호실과 날짜별 예약 가능 시간 (실제 예약은 중앙도서관 앱에서)."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_catalog, get_optional_user, get_provider, joined_members, my_membership
from app.models import Group, User
from app.occupancy import booked_map, hour_taken
from app.places.catalog import Catalog, Place
from app.places.provider import ProviderUnavailable, ReservationProvider
from app.schemas import RoomAvailabilityOut, RoomOut, SlotOut, SlotState
from app.services.booking import MSG_WINDOW, booking_window, is_past
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
    summary="날짜별 호실 시간 상태 (오늘부터 7일)",
)
def rooms_availability(
    day: date = Query(alias="date"),
    group_id: str | None = Query(default=None, alias="groupId"),
    catalog: Catalog = Depends(get_catalog),
    provider: ReservationProvider = Depends(get_provider),
    user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    now = now_kst()
    first, last = booking_window(now)
    if not first <= day <= last:
        raise HTTPException(422, MSG_WINDOW)
    group = None
    if group_id:
        # groupId를 주면 그 모임 인원이 들어가는 방인지(fitsGroup) 알려준다. 참여한 팀원만
        if user is None:
            raise HTTPException(401, "로그인이 필요해요.", headers={"WWW-Authenticate": "Bearer"})
        group = db.get(Group, group_id)
        if group is None or my_membership(db, group_id, user) is None:
            raise HTTPException(404, "모임을 찾을 수 없어요.")
    rooms = list(catalog.rooms)
    try:
        booked = booked_map(provider, rooms, day)
    except ProviderUnavailable as e:
        raise HTTPException(503, str(e)) from e

    result = []
    for room in rooms:
        fits = None if group is None else len(joined_members(group)) <= room.capacity
        slots = []
        for h in HOURS:
            state: SlotState
            if is_past(day, h, now):
                state = "past"
            elif hour_taken(booked.get(room.id, []), h):
                state = "occupied"
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
