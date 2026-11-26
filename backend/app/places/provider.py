"""집현전 예약 현황(이미 차 있는 시간) 조회.

추천·예약 로직은 ReservationProvider 인터페이스에만 의존한다.
- SeedReservationProvider: 프론트 isSeedOccupied()와 같은 계산식의 시연용 점유.
  앱과 서버의 '예약됨' 표시가 일치한다.
- JiphyeonjeonProvider: 실제 집현전 현황 조회 (app/places/jiphyeonjeon.py, 학교 비공개 API)
"""

import re
from collections.abc import Mapping, Sequence
from datetime import date, time
from typing import TYPE_CHECKING, Protocol

from app.places.catalog import Room
from app.timetable import HOURS

if TYPE_CHECKING:
    from app.places.jiphyeonjeon import JiphyeonjeonClient

Booked = list[tuple[time, time]]


class ProviderUnavailable(Exception):
    """예약 현황을 지금 가져올 수 없음 → API는 503으로 응답한다.

    메시지는 사용자에게 그대로 보여준다.
    """


class ReservationProvider(Protocol):
    def get_booked(self, rooms: Sequence[Room], day: date) -> dict[str, Booked]:
        """호실 id → 그 날 이미 차 있는 (시작, 끝) 목록"""
        ...


def seed_occupied(room_id: str, day: date | str, hour: int) -> bool:
    """프론트 src/domain/booking.ts의 isSeedOccupied()를 그대로 옮긴 것.

    JS 원본:
        let hash = 5381;
        for (const char of `${roomId}|${date}`) hash = ((hash * 33) ^ char.charCodeAt(0)) >>> 0;
        return (hash + hour * 17) % 7 < 2;
    """
    key = f"{room_id}|{day if isinstance(day, str) else day.isoformat()}"
    h = 5381
    for ch in key:
        h = (((h * 33) & 0xFFFFFFFF) ^ ord(ch)) & 0xFFFFFFFF
    return (h + hour * 17) % 7 < 2


def _hour_range(hour: int) -> tuple[time, time]:
    return time(hour, 0), time(hour + 1, 0) if hour < 23 else time(23, 59)


class SeedReservationProvider:
    """시연용 점유 (프론트와 같은 결과)"""

    def get_booked(self, rooms: Sequence[Room], day: date) -> dict[str, Booked]:
        return {r.id: [_hour_range(h) for h in HOURS if seed_occupied(r.id, day, h)] for r in rooms}


class StaticReservationProvider:
    """직접 넣어준 점유만 있는 조회기 (테스트용)."""

    def __init__(self, bookings: Mapping[tuple[str, date], Booked] | None = None):
        self.bookings = dict(bookings or {})

    def add(self, room_id: str, day: date, start: time, end: time) -> None:
        self.bookings.setdefault((room_id, day), []).append((start, end))

    def get_booked(self, rooms: Sequence[Room], day: date) -> dict[str, Booked]:
        return {r.id: list(self.bookings.get((r.id, day), [])) for r in rooms}


def school_room_no(room: Room) -> str:
    """학교 API의 방 번호. places.json의 source_room_no가 없으면 이름의 숫자(집현 4실 → 4)"""
    return room.source_room_no or re.sub(r"\D", "", room.name)


class JiphyeonjeonProvider:
    """실제 집현전 예약 가능 맵을 읽어 '차 있는 시간'으로 바꿔준다.

    예약 불가인 칸과 맵에 없는 시간(운영 시간 밖)은 모두 차 있는 것으로 본다.
    """

    def __init__(self, client: "JiphyeonjeonClient"):
        self.client = client

    def get_booked(self, rooms: Sequence[Room], day: date) -> dict[str, Booked]:
        from app.places.jiphyeonjeon import busy_from_slots

        return {
            r.id: busy_from_slots(self.client.room_slots(school_room_no(r), day)) for r in rooms
        }


def build_provider(
    name: str,
    *,
    status_url: str | None = None,
    map_url: str | None = None,
    cache_seconds: float = 180,
    timeout: float = 5.0,
) -> ReservationProvider:
    if name == "mock":
        return SeedReservationProvider()
    if name == "jiphyeonjeon":
        from app.places.jiphyeonjeon import JiphyeonjeonClient

        client = JiphyeonjeonClient(
            status_url, map_url, timeout=timeout, cache_seconds=cache_seconds
        )
        return JiphyeonjeonProvider(client)
    raise ValueError(f"알 수 없는 RESERVATION_PROVIDER: {name}")
