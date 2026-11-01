"""장소(places)와 예약 가능한 호실(rooms).

- Place: 프론트 PLACES와 같은 필드 (장소 목록·상세 화면용)
- Room : 프론트 ROOMS (집현전 201·202·301·302호) + AI 조건 추천용 속성(콘센트·소음 등)

다른 학교에서 쓸 때는 data/places.json만 바꾸면 된다.
"""

import json
from dataclasses import dataclass
from datetime import time
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

RoomType = Literal["study_room", "reading_room"]
NoiseLevel = Literal["quiet", "normal"]

ROOM_TYPE_LABEL: dict[str, str] = {"study_room": "스터디룸", "reading_room": "열람실"}


class Place(BaseModel):
    id: str
    name: str
    category: Literal["교내", "카페"]
    location: str
    capacity: int
    tags: list[str]
    description: str
    note: str
    reservable: bool


class Room(BaseModel):
    id: str
    place_id: str
    name: str  # 예: 201호
    full_name: str = ""  # 예: 집현전 201호 (불러올 때 채움)
    capacity: int
    room_type: RoomType = "study_room"
    has_outlet: bool = False
    noise_level: NoiseLevel = "normal"
    laptop_space: bool = False
    # 예약 슬롯은 09:00~19:00 (프론트 HOURS)
    open_time: time = time(9, 0)
    close_time: time = time(19, 0)
    reservable: bool = True


@dataclass(frozen=True)
class Catalog:
    places: tuple[Place, ...]
    rooms: tuple[Room, ...]

    def room(self, room_id: str) -> Room | None:
        return next((r for r in self.rooms if r.id == room_id), None)

    def place(self, place_id: str) -> Place | None:
        return next((p for p in self.places if p.id == place_id), None)


def load_catalog(path: Path) -> Catalog:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    places = tuple(Place.model_validate(p) for p in raw["places"])
    names = {p.id: p.name for p in places}
    rooms = []
    for r in raw["rooms"]:
        room = Room.model_validate(r)
        if room.place_id not in names:
            raise ValueError(f"호실 {room.id}의 place_id({room.place_id})가 places에 없어요")
        rooms.append(room.model_copy(update={"full_name": f"{names[room.place_id]} {room.name}"}))
    return Catalog(places, tuple(rooms))


@lru_cache
def load_catalog_cached(path: str) -> Catalog:
    return load_catalog(Path(path))
