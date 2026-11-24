"""광운대 중앙도서관 집현전(스터디룸) 현황 조회 연동.

학교 비공개 API, 사용 전 확인 필요.
- 주소는 코드에 쓰지 않는다.
  backend/.env의 JIPHYEONJEON_STATUS_URL, JIPHYEONJEON_MAP_URL로만 받는다.
- 조회만 한다 (로그인·학번 없음). 실제 예약은 사용자가 도서관 앱에서 한다.
- 학교 서버 부담을 줄이려고 같은 요청은 cache_seconds(기본 3분) 동안 캐시를 재사용하고,
  호출이 실패하면 retry_after_seconds 동안 학교 서버를 다시 부르지 않는다.
- 응답은 XML이다. 외부에서 받은 XML이라 defusedxml로 안전하게 파싱한다.

[실제 응답으로 확인한 형식] (2026-11-17·18, 도서관 앱 화면과 대조)
방별 현황: 방 하나가 아니라 종류별로 온다. room_no 4 = 4인실, 6 = 6인실, 10 = 10인실.
예약 가능 맵 (room_seat_no = 위 종류 번호, search_date = YYYYMMDD):
    room_no_0~3 / room_name_0~3   그 종류의 방 이름 (칸이 4개뿐)
    <time_list>                   시간마다 반복. 09시~22시, 1시간 단위
      <time_period>09000955</time_period>
      <time_period_arr_0>0</time_period_arr_0>   i번째 칸 = i번째 방 (room_no_i)
      …                                           이름 칸(4개)을 넘는 칸은 번호를 이어 붙인다
      <time_period_arr_5></time_period_arr_5>     빈칸이면 그 자리에 방이 없음
    </time_list>
    select_day_01~07 = 예약할 수 있는 날짜 목록(오늘~6일 뒤). 시간대 정보가 아니다.
    값: 0 = 예약 가능, 5 = 예약됨, 7 = 사용 중(추정), 10 = 지난 시간(추정)
    종류 번호가 아닌 번호(1, 8, 13 …)로 조회하면 전부 빈칸으로 온다.

실제 방 (13개): 4 → 4·5·6·7·8·9실, 6 → 2·3·12실, 10 → 1·13실.
4인실 10·11실은 한 번에 6칸까지만 와서 이 API로는 알 수 없다 → places.json 호실 목록에서 뺐다.

예약 가능은 값이 0일 때뿐이다. 모르는 값이 오면 '예약 불가'로 보고 로그를 남긴다
(예약된 방을 '가능'으로 잘못 보여주지 않기 위해).
"""

import logging
import re
import threading
import time as clock
from collections.abc import Callable, Hashable
from dataclasses import dataclass
from datetime import date, time
from typing import Any, TypeVar
from xml.etree.ElementTree import Element

import httpx
from defusedxml import DefusedXmlException
from defusedxml import ElementTree as SafeET

from app.places.provider import ProviderUnavailable

log = logging.getLogger(__name__)

# ---------- 확인한 값 ----------
CODE_AVAILABLE = "0"
CODE_LABELS = {"0": "가능", "5": "예약됨", "7": "사용중", "10": "지남"}

STALE_MAX_SECONDS = 15 * 60  # 학교 서버가 안 될 때 이 시간까지는 지난 캐시를 대신 쓴다
USER_AGENT = "TeamPlus-backend (KW Meet student project)"

_PERIOD = re.compile(r"^(\d{2})(\d{2})(\d{2})(\d{2})$")
_ARR = re.compile(r"^time_period_arr_(\d+)$")
_ROOM_NO = re.compile(r"^room_no_(\d+)$")


class JiphyeonjeonFormatError(Exception):
    """응답이 확인한 XML 형식과 다름 (학교 API가 바뀌었을 수 있음. probe 스크립트로 확인)"""


@dataclass(frozen=True)
class RoomStatus:
    """종류별 현재 현황 (연동 안내 문서의 1번 API). 예: 그룹학습실 4인실 8개 중 8개 사용 중"""

    room_no: str
    name: str
    total_seat: int | None
    use_seat: int | None
    remain_seat: int | None
    open_time: str | None
    close_time: str | None
    holiday: bool
    holiday_msg: str | None


@dataclass(frozen=True)
class Slot:
    start: time
    end: time
    available: bool


# ---------- XML 파싱 ----------
_DECL_ENCODING = re.compile(rb"""^\s*<\?xml[^>]*encoding=["']([\w.-]+)["']""")
_KOREAN = {"euc-kr", "euckr", "ks_c_5601-1987", "cp949", "ms949"}


def _parse_xml(raw: bytes) -> Element:
    try:
        try:
            return SafeET.fromstring(raw)
        except DefusedXmlException:  # ValueError의 하위 클래스라 먼저 걸러낸다
            raise
        except (SafeET.ParseError, ValueError):
            pass
        # expat은 EUC-KR 같은 멀티바이트 인코딩을 못 읽는다 → 직접 풀어서 UTF-8로 다시 파싱
        # (선언이 없으면 학교 서버에서 흔한 CP949로 본다)
        m = _DECL_ENCODING.match(raw)
        enc = m.group(1).decode().lower() if m else "cp949"
        text = raw.decode("cp949" if enc in _KOREAN else enc)
        text = re.sub(r"^\s*<\?xml[^>]*\?>", "", text)
        return SafeET.fromstring(text.encode("utf-8"))
    except DefusedXmlException as e:  # 외부 엔티티 등 위험한 XML
        raise JiphyeonjeonFormatError(f"허용하지 않는 XML이에요: {e.__class__.__name__}") from e
    except (UnicodeDecodeError, LookupError, SafeET.ParseError, ValueError) as e:
        raise JiphyeonjeonFormatError(f"XML이 아니에요: {raw[:200]!r}") from e


def _text(el: Element | None) -> str | None:
    if el is None or el.text is None:
        return None
    t = el.text.strip()
    return t or None


def _int(v: str | None) -> int | None:
    try:
        return int(v) if v is not None else None
    except ValueError:
        return None


def parse_room_status(raw: bytes) -> list[RoomStatus]:
    """방마다 room_no·room_name·total_seat … 이 반복되는 XML → RoomStatus 목록"""
    root = _parse_xml(raw)
    rooms = []
    for el in root.iter():
        if el.find("room_no") is None:
            continue
        f = {child.tag: _text(child) for child in el}
        holiday = (f.get("chk_holiday") or "").upper() in {"Y", "1", "TRUE"}
        rooms.append(
            RoomStatus(
                room_no=f.get("room_no") or "",
                name=f.get("room_name") or f.get("room_e_name") or "",
                total_seat=_int(f.get("total_seat")),
                use_seat=_int(f.get("use_seat")),
                remain_seat=_int(f.get("remain_seat")),
                open_time=f.get("time_start"),
                close_time=f.get("time_end"),
                holiday=holiday,
                holiday_msg=f.get("holiday_msg"),
            )
        )
    if not rooms:
        raise JiphyeonjeonFormatError("room_no가 있는 항목이 없어요")
    return rooms


def leaf_fields(raw: bytes) -> list[tuple[str, str | None]]:
    """응답의 모든 (태그, 값). 확인 스크립트에서 실제 형식을 볼 때 쓴다."""
    root = _parse_xml(raw)
    return [(el.tag, _text(el)) for el in root.iter() if len(el) == 0]


@dataclass(frozen=True)
class RoomMap:
    """예약 가능 맵 한 번의 응답"""

    hours: list[int]  # 시작 시각 (9 = 09:00~09:55)
    codes: dict[str, list[str]]  # 방 번호 → 시간별 값
    names: dict[str, str]  # 응답에 들어 있던 방 이름 (참고용)


def parse_map_codes(raw: bytes) -> RoomMap:
    """시간별 time_period_arr_i 값을 방 번호별로 모은다.

    i번째 칸 = room_no_i. 이름 칸이 4개뿐이라 그 뒤 칸은 앞 방 번호에 1씩 더한다 (4인실: 8·9실).
    값이 하나도 없는 칸은 방이 없는 자리라 버린다.
    """
    root = _parse_xml(raw)
    names: dict[int, tuple[str, str]] = {}
    for el in root.iter():
        r = _ROOM_NO.match(el.tag)
        if r and _text(el):
            i = int(r.group(1))
            names[i] = (_text(el), _text(root.find(f".//room_name_{i}")) or "")

    hours: list[int] = []
    columns: dict[int, list[str]] = {}
    for tl in root.iter("time_list"):
        period = _text(tl.find("time_period")) or ""
        m = _PERIOD.match(period)
        if not m or not 0 <= int(m.group(1)) <= 23:
            raise JiphyeonjeonFormatError(f"time_period 형식이 달라요: {period!r}")
        hours.append(int(m.group(1)))
        for el in tl:
            a = _ARR.match(el.tag)
            if a:
                columns.setdefault(int(a.group(1)), []).append(_text(el) or "")
    if not hours:
        raise JiphyeonjeonFormatError("time_list가 없어요")
    if any(len(v) != len(hours) for v in columns.values()):
        raise JiphyeonjeonFormatError("시간마다 칸 개수가 달라요")

    codes: dict[str, list[str]] = {}
    prev: str | None = None
    for i in sorted(columns):
        values = columns[i]
        if not any(values):
            prev = None
            continue  # 방이 없는 칸
        if i in names:
            room = names[i][0]
        elif prev is not None and prev.isdigit():
            room = str(int(prev) + 1)  # 이름 칸을 넘는 칸: 번호를 이어 붙임
        else:
            raise JiphyeonjeonFormatError(f"{i}번째 칸이 어느 방인지 알 수 없어요")
        codes[room] = values
        prev = room
    return RoomMap(hours, codes, {no: name for no, name in names.values()})


def parse_room_map(raw: bytes) -> dict[str, list[Slot]]:
    """예약 가능 맵 XML → 방 번호별 1시간 Slot 목록. 값이 0인 칸만 예약 가능"""
    rmap = parse_map_codes(raw)
    unknown = {c for v in rmap.codes.values() for c in v if c not in CODE_LABELS}
    if unknown:
        log.warning("집현전 맵에 모르는 값 %s → 예약 불가로 처리", sorted(unknown))
    return {
        room: [
            # 끝이 HH:55라도 1시간 칸으로 본다 (5분은 정리 시간)
            Slot(time(h), _t((h + 1) * 60), code == CODE_AVAILABLE)
            for h, code in zip(rmap.hours, values, strict=True)
        ]
        for room, values in rmap.codes.items()
    }


def _t(minutes: int) -> time:
    return time(23, 59) if minutes >= 24 * 60 else time(minutes // 60, minutes % 60)


def busy_from_slots(slots: list[Slot]) -> list[tuple[time, time]]:
    """예약 가능한 칸을 뺀 나머지를 전부 '차 있음'으로 본다.

    맵에 없는 시간(운영 시간 밖 등)도 예약할 수 없는 것으로 처리한다.
    """
    free = sorted(
        (s.start.hour * 60 + s.start.minute, s.end.hour * 60 + s.end.minute)
        for s in slots
        if s.available
    )
    busy, cursor = [], 0
    for start, end in free:
        if start > cursor:
            busy.append((_t(cursor), _t(start)))
        cursor = max(cursor, end)
    if cursor < 24 * 60:
        busy.append((_t(cursor), _t(24 * 60)))
    return busy


# ---------- 캐시 ----------
T = TypeVar("T")


class _Cache:
    """키별 TTL 캐시. 같은 키를 여러 요청이 동시에 찾아도 학교 서버는 한 번만 부른다."""

    def __init__(self, ttl: float, now: Callable[[], float]):
        self.ttl = ttl
        self.now = now
        self._data: dict[Hashable, tuple[float, Any]] = {}
        self._locks: dict[Hashable, threading.Lock] = {}
        self._guard = threading.Lock()

    def fresh(self, key: Hashable) -> Any | None:
        hit = self._data.get(key)
        return hit[1] if hit and self.now() - hit[0] < self.ttl else None

    def stale(self, key: Hashable, max_age: float) -> Any | None:
        hit = self._data.get(key)
        return hit[1] if hit and self.now() - hit[0] < max_age else None

    def put(self, key: Hashable, value: Any) -> None:
        self._data[key] = (self.now(), value)
        if len(self._data) > 2000:  # 오래된 항목 정리
            cutoff = self.now() - STALE_MAX_SECONDS
            self._data = {k: v for k, v in self._data.items() if v[0] >= cutoff}

    def lock(self, key: Hashable) -> threading.Lock:
        with self._guard:
            return self._locks.setdefault(key, threading.Lock())


# ---------- 클라이언트 ----------
MSG_UNAVAILABLE = "집현전 예약 현황을 불러오지 못했어요. 잠시 후 다시 시도해 주세요."


class JiphyeonjeonClient:
    def __init__(
        self,
        status_url: str | None,
        map_url: str | None,
        *,
        timeout: float = 5.0,
        cache_seconds: float = 180,
        retry_after_seconds: float = 60,
        http: httpx.Client | None = None,
        now: Callable[[], float] = clock.monotonic,
    ):
        self.status_url = status_url
        self.map_url = map_url
        self.retry_after = retry_after_seconds
        self.now = now
        self._cache = _Cache(cache_seconds, now)
        self._down_until = 0.0
        self._missing_logged: set[str] = set()
        self._http = http or httpx.Client(
            timeout=timeout,
            headers={"User-Agent": USER_AGENT},
            follow_redirects=False,
        )

    def room_status(self) -> list[RoomStatus]:
        """방별 현재 현황 (3분 캐시)"""
        url = self._require(self.status_url, "JIPHYEONJEON_STATUS_URL")
        return self._cached("status", lambda: parse_room_status(self._post(url, None)))

    def room_slots(self, room_no: str, day: date) -> list[Slot]:
        """방 하나의 그 날 시간대별 예약 가능 여부 (3분 캐시).

        학교 API는 종류(4·6·10)별로 조회하고 한 번에 그 종류의 방들이 같이 온다.
        종류 번호는 방별 현황에서 읽는다. 날짜당 학교 서버 호출은 최대 3번(+ 현황 1번).
        응답에 없는 방(4인실 10·11실 등)은 알 수 없으므로 예약 가능한 시간이 없는 것으로 본다.
        """
        hit = self._cache.fresh(("room", room_no, day))
        if hit is not None:
            return hit
        for group in [s.room_no for s in self.room_status() if s.room_no]:
            rooms = self._group_rooms(group, day)
            if room_no in rooms:
                return rooms[room_no]
        if room_no not in self._missing_logged:
            self._missing_logged.add(room_no)
            log.warning("집현전 응답에 %s실이 없어요 → 예약 불가로 처리", room_no)
        return []

    def _group_rooms(self, group: str, day: date) -> dict[str, list[Slot]]:
        url = self._require(self.map_url, "JIPHYEONJEON_MAP_URL")
        form = {"room_seat_no": group, "search_date": day.strftime("%Y%m%d")}

        def fetch() -> dict[str, list[Slot]]:
            rooms = parse_room_map(self._post(url, form))
            if not rooms:
                log.warning("집현전 %s번 조회 결과가 비어 있어요", group)
            return rooms

        rooms = self._cached(("map", group, day), fetch)
        for other, slots in rooms.items():
            if self._cache.fresh(("room", other, day)) is None:
                self._cache.put(("room", other, day), slots)
        return rooms

    def raw(self, which: str, form: dict[str, str] | None = None) -> bytes:
        """캐시 없이 원본 응답 (확인 스크립트 전용)"""
        url = self.status_url if which == "status" else self.map_url
        return self._post(self._require(url, f"JIPHYEONJEON_{which.upper()}_URL"), form)

    # --- 내부 ---
    @staticmethod
    def _require(url: str | None, env: str) -> str:
        if not url:
            raise ProviderUnavailable(
                f"집현전 연동 설정({env})이 없어요. backend/.env를 확인하세요."
            )
        return url

    def _post(self, url: str, form: dict[str, str] | None) -> bytes:
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        if form is None:
            resp = self._http.post(url, content=b"", headers=headers)
        else:
            resp = self._http.post(url, data=form, headers=headers)
        resp.raise_for_status()
        return resp.content

    def _cached(self, key: Hashable, fetch: Callable[[], T]) -> T:
        value = self._cache.fresh(key)
        if value is not None:
            return value
        with self._cache.lock(key):
            value = self._cache.fresh(key)  # 기다리는 동안 다른 요청이 채웠을 수 있음
            if value is not None:
                return value
            if self.now() < self._down_until:
                return self._fallback(key, None)
            try:
                value = fetch()
            except (httpx.HTTPError, JiphyeonjeonFormatError) as e:
                # 학교 서버가 안 되면 retry_after 동안 모든 키에 대해 다시 부르지 않는다
                self._down_until = self.now() + self.retry_after
                return self._fallback(key, e)
            self._cache.put(key, value)
            return value

    def _fallback(self, key: Hashable, error: Exception | None) -> Any:
        if error is not None:
            detail = error.__class__.__name__
            if isinstance(error, httpx.HTTPStatusError):
                detail += f" {error.response.status_code}"
            elif isinstance(error, JiphyeonjeonFormatError):
                detail += f": {error}"  # 학교 응답 형식이 바뀜. probe 스크립트로 확인
            log.warning("집현전 조회 실패 (%s) key=%s", detail, key)
        stale = self._cache.stale(key, STALE_MAX_SECONDS)
        if stale is not None:
            log.info("집현전 지난 캐시 사용 key=%s", key)
            return stale
        raise ProviderUnavailable(MSG_UNAVAILABLE) from error
