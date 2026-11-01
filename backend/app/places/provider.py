"""집현전 예약 현황(이미 차 있는 시간) 조회.

추천·예약 로직은 ReservationProvider 인터페이스에만 의존한다.
- SeedReservationProvider: 프론트 isSeedOccupied()와 같은 계산식의 시연용 점유.
  앱과 서버의 '예약됨' 표시가 일치한다.
- JiphyeonjeonProvider: 실제 집현전 연동 자리 (구현 예정)
사용자가 이 서비스에서 만든 예약(DB)은 여기가 아니라 reservations 테이블에서 따로 합친다.
"""

from collections.abc import Mapping, Sequence
from datetime import date, time
from typing import Protocol

from app.places.catalog import Room
from app.timetable import HOURS

Booked = list[tuple[time, time]]


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


class JiphyeonjeonProvider:
    """실제 광운대 중앙도서관 집현전 예약 현황 연동 자리.

    TODO: '집현전 현황 조회 API 연동 안내' 문서 확인 후 구현.
    - 실제 방 ID 매핑, 그 날 예약된 시간대를 (time, time) 목록으로 돌려줄 것
    - 학생 계정 비밀번호를 서버에 저장하는 방식은 피할 것
    - 응답은 짧게(예: 1~5분) 캐시해서 호출 수를 줄일 것
    """

    def get_booked(self, rooms: Sequence[Room], day: date) -> dict[str, Booked]:
        raise NotImplementedError(
            "집현전 연동은 아직 구현되지 않았어요. RESERVATION_PROVIDER=mock을 쓰세요."
        )


def build_provider(name: str) -> ReservationProvider:
    if name == "mock":
        return SeedReservationProvider()
    if name == "jiphyeonjeon":
        return JiphyeonjeonProvider()
    raise ValueError(f"알 수 없는 RESERVATION_PROVIDER: {name}")
