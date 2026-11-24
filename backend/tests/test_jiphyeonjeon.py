"""집현전 현황 조회 연동 테스트. 실제 학교 서버 대신 가짜 응답(httpx.MockTransport)을 쓴다.

응답 형식은 2026-11-17·18에 받은 실제 응답과 같다.
종류 번호(4·6·10)로 조회하면 그 종류의 방들이 칸으로 온다 (4 → 4~9실, 6 → 2·3·12실, 10 → 1·13실).
"""

import threading
import time as real_time
from datetime import date, time, timedelta
from urllib.parse import parse_qs

import httpx
import pytest

from app import deps
from app.main import app
from app.occupancy import hour_taken
from app.places.catalog import Room
from app.places.jiphyeonjeon import (
    MSG_UNAVAILABLE,
    JiphyeonjeonClient,
    JiphyeonjeonFormatError,
    busy_from_slots,
    parse_map_codes,
    parse_room_map,
    parse_room_status,
)
from app.places.provider import JiphyeonjeonProvider, ProviderUnavailable, school_room_no
from app.timeutil import today_kst
from tests.conftest import signup

STATUS_URL = "https://school.invalid/status"  # 가짜 주소 (실제 주소는 .env에만)
MAP_URL = "https://school.invalid/map"
TOMORROW = today_kst() + timedelta(days=1)
HOURS = list(range(9, 23))  # 학교 맵의 시간 칸: 09~22시
FREE = ["0"] * len(HOURS)
# 실제 학교 구성: 종류 번호 → (이름 칸에 오는 방, 값 칸에 오는 방)
GROUPS = {
    "4": (["4", "5", "6", "7"], ["4", "5", "6", "7", "8", "9"]),
    "6": (["2", "3", "12"], ["2", "3", "12"]),
    "10": (["1", "13"], ["1", "13"]),
}


def codes(**booked) -> list[str]:
    """시간별 값 목록. codes(h10="5") → 10시만 예약됨, 나머지 가능"""
    return [booked.get(f"h{h}", "0") for h in HOURS]


def map_xml(names: list[str], columns: list[list[str]]) -> bytes:
    """실제 응답과 같은 모양: 이름 칸 4개, 값 칸 6개 (없는 자리는 빈칸)"""
    head = "".join(
        f"<room_no_{i}><![CDATA[{names[i] if i < len(names) else ''}]]></room_no_{i}>"
        f"<room_name_{i}><![CDATA[{'집현 ' + names[i] + '실' if i < len(names) else ''}]]>"
        f"</room_name_{i}>"
        for i in range(4)
    )
    days = "".join(
        f"<select_day_{i:02d}>{TOMORROW + timedelta(days=i):%Y%m%d}</select_day_{i:02d}>"
        for i in range(1, 8)
    )
    cols = columns + [[""] * len(HOURS)] * (6 - len(columns))
    lists = "".join(
        f"<time_list><time_period><![CDATA[{h:02d}00{h:02d}55]]></time_period>"
        + "".join(
            f"<time_period_arr_{i}><![CDATA[{col[k]}]]></time_period_arr_{i}>"
            for i, col in enumerate(cols)
        )
        + "</time_list>"
        for k, h in enumerate(HOURS)
    )
    body = f"<root><item>{head}{days}{lists}</item></root>"
    return ("<?xml version='1.0' encoding='utf-8'?>" + body).encode()


EMPTY_XML = map_xml([], [])  # 종류 번호가 아닌 번호로 조회했을 때 (실제로 전부 빈칸)

# 실제 응답처럼 root 안에 글자가 섞여 있다
STATUS_XML = """<?xml version='1.0' encoding='utf-8'?>
<root>4<item><room_no><![CDATA[4]]></room_no><room_name><![CDATA[그룹학습실 4 인실]]></room_name><chk_holiday><![CDATA[N]]></chk_holiday><holiday_msg><![CDATA[]]></holiday_msg><total_seat><![CDATA[8]]></total_seat><use_seat><![CDATA[8]]></use_seat><remain_seat><![CDATA[0]]></remain_seat></item>6<item><room_no><![CDATA[6]]></room_no><room_name><![CDATA[그룹학습실 6 인실]]></room_name><chk_holiday><![CDATA[N]]></chk_holiday><total_seat><![CDATA[3]]></total_seat><use_seat><![CDATA[1]]></use_seat><remain_seat><![CDATA[2]]></remain_seat></item>10<item><room_no><![CDATA[10]]></room_no><room_name><![CDATA[그룹학습실 10인실]]></room_name><chk_holiday><![CDATA[Y]]></chk_holiday><holiday_msg><![CDATA[정기 휴관]]></holiday_msg><total_seat><![CDATA[2]]></total_seat><use_seat><![CDATA[2]]></use_seat><remain_seat><![CDATA[0]]></remain_seat></item></root>"""  # noqa: E501


class FakeSchool:
    """가짜 학교 서버. 종류 번호로 조회하면 그 종류 방들의 시간별 값을 돌려준다."""

    def __init__(self):
        self.calls: list[dict] = []
        self.rooms: dict[str, list[str]] = {}  # 방 번호 → 시간별 값 (없으면 전부 가능)
        self.fail: Exception | int | None = None
        self.delay = 0.0

    def map_calls(self) -> list[str]:
        return [c["form"]["room_seat_no"] for c in self.calls if c["url"] == MAP_URL]

    def handler(self, request: httpx.Request) -> httpx.Response:
        form = {k: v[0] for k, v in parse_qs(request.content.decode()).items()}
        self.calls.append({"url": str(request.url), "form": form})
        if self.delay:
            real_time.sleep(self.delay)
        if isinstance(self.fail, Exception):
            raise self.fail
        if isinstance(self.fail, int):
            return httpx.Response(self.fail)
        if str(request.url) == STATUS_URL:
            return httpx.Response(200, content=STATUS_XML.encode())
        group = GROUPS.get(form["room_seat_no"])
        if group is None:
            return httpx.Response(200, content=EMPTY_XML)
        names, rooms = group
        return httpx.Response(200, content=map_xml(names, [self.rooms.get(r, FREE) for r in rooms]))


class FakeClock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t


@pytest.fixture
def school():
    return FakeSchool()


@pytest.fixture
def fake_clock():
    return FakeClock()


@pytest.fixture
def jclient(school, fake_clock):
    http = httpx.Client(transport=httpx.MockTransport(school.handler))
    return JiphyeonjeonClient(STATUS_URL, MAP_URL, http=http, now=fake_clock)


# ---------- 파싱 (실제 형식) ----------
def test_four_person_rooms_continue_past_name_slots():
    # 4로 조회: 이름은 4~7실만 오지만 값은 6칸 = 4~9실
    raw = map_xml(["4", "5", "6", "7"], [FREE, codes(h10="5"), FREE, FREE, FREE, codes(h12="5")])
    rmap = parse_map_codes(raw)
    assert list(rmap.codes) == ["4", "5", "6", "7", "8", "9"]
    assert rmap.hours == HOURS
    assert rmap.names == {"4": "집현 4실", "5": "집현 5실", "6": "집현 6실", "7": "집현 7실"}
    rooms = parse_room_map(raw)
    five = {s.start.hour: s for s in rooms["5"]}
    assert (five[10].start, five[10].end, five[10].available) == (time(10), time(11), False)
    assert five[9].available and five[11].available
    assert not {s.start.hour: s for s in rooms["9"]}[12].available


def test_six_and_ten_person_rooms_follow_name_order():
    # 6으로 조회: 2·3·12실 (번호가 이어지지 않음), 나머지 칸은 빈칸
    rooms = parse_room_map(map_xml(["2", "3", "12"], [FREE, codes(h10="5"), codes(h9="5")]))
    assert list(rooms) == ["2", "3", "12"]
    assert not {s.start.hour: s.available for s in rooms["12"]}[9]
    assert list(parse_room_map(map_xml(["1", "13"], [FREE, FREE]))) == ["1", "13"]


def test_wrong_number_gives_empty_map():
    assert parse_room_map(EMPTY_XML) == {}


def test_codes_only_zero_is_available(caplog):
    col = codes(h9="0", h10="5", h11="7", h12="10", h13="3")  # 3 = 처음 보는 값
    slots = {s.start.hour: s.available for s in parse_room_map(map_xml(["4"], [col]))["4"]}
    assert slots[9] is True
    assert slots[10] is slots[11] is slots[12] is False
    assert slots[13] is False  # 모르는 값은 예약 불가로
    assert "모르는 값 ['3']" in caplog.text


def test_busy_hours_for_our_one_hour_slots():
    slots = parse_room_map(map_xml(["4"], [codes(h10="5", h15="7")]))["4"]
    busy = busy_from_slots(slots)
    assert not hour_taken(busy, 9)
    assert hour_taken(busy, 10)  # 예약됨
    assert hour_taken(busy, 15)  # 사용 중
    assert not hour_taken(busy, 18)
    assert hour_taken(busy, 23)  # 맵에 없는 시간은 예약 불가


def test_unexpected_format_stops():
    with pytest.raises(JiphyeonjeonFormatError, match="time_list"):
        parse_room_map(b"<root><item><select_day_01>20261119</select_day_01></item></root>")
    with pytest.raises(JiphyeonjeonFormatError, match="time_period"):
        parse_room_map(b"<root><time_list><time_period>9am</time_period></time_list></root>")
    with pytest.raises(JiphyeonjeonFormatError, match="XML"):
        parse_room_map(b"<html>error page")


def test_room_status_by_type():
    rooms = parse_room_status(STATUS_XML.encode())
    assert [(r.room_no, r.name, r.total_seat, r.remain_seat, r.holiday) for r in rooms] == [
        ("4", "그룹학습실 4 인실", 8, 0, False),
        ("6", "그룹학습실 6 인실", 3, 2, False),
        ("10", "그룹학습실 10인실", 2, 0, True),
    ]
    assert rooms[2].holiday_msg == "정기 휴관"


@pytest.mark.parametrize("declared", [True, False])
def test_euc_kr_response(declared):
    body = STATUS_XML.replace("utf-8", "euc-kr") if declared else STATUS_XML.split("\n", 1)[1]
    assert parse_room_status(body.encode("cp949"))[0].name == "그룹학습실 4 인실"


def test_external_entities_are_rejected():
    evil = (
        b'<?xml version="1.0"?><!DOCTYPE r [<!ENTITY x SYSTEM "file:///etc/passwd">]>'
        b"<root><time_list><time_period>&x;</time_period></time_list></root>"
    )
    with pytest.raises(JiphyeonjeonFormatError, match="허용하지 않는"):
        parse_room_map(evil)


# ---------- 호출·캐시 ----------
def test_all_rooms_take_three_map_calls_per_day(jclient, school):
    day = date(2026, 11, 19)
    for n in range(1, 14):
        jclient.room_slots(str(n), day)
    assert school.map_calls() == ["4", "6", "10"]  # 종류별로 한 번씩
    assert [c["form"]["search_date"] for c in school.calls if c["url"] == MAP_URL] == [
        "20261119"
    ] * 3
    assert sum(c["url"] == STATUS_URL for c in school.calls) == 1


def test_rooms_10_and_11_are_unknown_so_never_available(jclient, school, caplog):
    assert jclient.room_slots("10", date(2026, 11, 19)) == []
    assert busy_from_slots([]) == [(time(0), time(23, 59))]
    assert "10실이 없어요" in caplog.text


def test_cache_expires_after_three_minutes(jclient, school, fake_clock):
    day = date(2026, 11, 19)
    jclient.room_slots("4", day)
    jclient.room_slots("9", day)  # 같은 응답에 들어 있음
    assert school.map_calls() == ["4"]
    fake_clock.t += 181
    jclient.room_slots("4", day)
    assert school.map_calls() == ["4", "4"]
    jclient.room_slots("4", date(2026, 11, 20))  # 다른 날짜는 따로
    assert school.map_calls() == ["4", "4", "4"]


def test_school_down_uses_recent_cache_then_stops_calling(jclient, school, fake_clock):
    day = date(2026, 11, 19)
    jclient.room_slots("4", day)
    fake_clock.t += 200  # 캐시 만료
    school.fail = 500

    # 학교 서버 오류 → 15분 안의 지난 값으로 대신 응답
    assert jclient.room_slots("4", day)[0].available
    calls = len(school.calls)

    # 1분 동안은 다른 날짜도 학교 서버를 부르지 않고 바로 503
    with pytest.raises(ProviderUnavailable, match="불러오지 못했어요"):
        jclient.room_slots("4", date(2026, 11, 20))
    assert len(school.calls) == calls

    # 1분 뒤 다시 시도. 학교 서버가 살아나면 정상
    fake_clock.t += 61
    school.fail = None
    assert jclient.room_slots("4", date(2026, 11, 20))
    assert len(school.calls) > calls


def test_timeout_without_cache_is_unavailable(jclient, school):
    school.fail = httpx.ConnectTimeout("timeout")
    with pytest.raises(ProviderUnavailable) as e:
        jclient.room_slots("4", date(2026, 11, 19))
    assert str(e.value) == MSG_UNAVAILABLE


def test_concurrent_requests_hit_school_once(school):
    school.delay = 0.05
    http = httpx.Client(transport=httpx.MockTransport(school.handler))
    client = JiphyeonjeonClient(STATUS_URL, MAP_URL, http=http)
    threads = [
        threading.Thread(target=client.room_slots, args=("4", date(2026, 11, 19))) for _ in range(5)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert school.map_calls() == ["4"]
    assert sum(c["url"] == STATUS_URL for c in school.calls) == 1


def test_missing_urls():
    client = JiphyeonjeonClient(None, None)
    with pytest.raises(ProviderUnavailable, match="JIPHYEONJEON_STATUS_URL"):
        client.room_slots("4", date(2026, 11, 19))


def test_room_number_mapping():
    base = {"id": "R4", "place_id": "jiphyeon", "name": "집현 4실", "capacity": 4}
    assert school_room_no(Room(**base)) == "4"
    assert school_room_no(Room(**base, source_room_no="12")) == "12"


# ---------- API까지 연결 (data/places.json의 실제 호실 사용) ----------
@pytest.fixture
def real_provider_client(client, jclient):
    app.dependency_overrides[deps.get_provider] = lambda: JiphyeonjeonProvider(jclient)
    client.headers.update(signup(client))
    return client


def test_room_availability_uses_school_data(real_provider_client, school):
    school.rooms["4"] = codes(h10="5")
    school.rooms["12"] = codes(h11="7")
    r = real_provider_client.get("/api/rooms/availability", params={"date": str(TOMORROW)})
    assert r.status_code == 200
    rooms = {x["roomId"]: {s["hour"]: s["state"] for s in x["slots"]} for x in r.json()}
    assert rooms["J04"][10] == "occupied" and rooms["J04"][11] == "available"
    assert rooms["J12"][11] == "occupied" and rooms["J12"][10] == "available"
    assert len(rooms) == 11
    # 날짜 하나에 종류별 3번 + 현황 1번
    assert school.map_calls() == ["4", "6", "10"]
    assert sum(c["url"] == STATUS_URL for c in school.calls) == 1


def test_recommendation_skips_slots_booked_at_school(real_provider_client, school):
    all_booked = ["5"] * len(HOURS)
    for n in (1, 2, 3, 4, 6, 7, 8, 9, 12, 13):
        school.rooms[str(n)] = all_booked
    school.rooms["5"] = [("0" if h == 12 else "5") for h in HOURS]  # 5실은 12시만 빔
    app.dependency_overrides[deps.get_llm] = lambda: None
    g = real_provider_client.post("/api/groups", json={"name": "캡스톤"}).json()
    r = real_provider_client.post(
        f"/api/groups/{g['id']}/recommendations",
        json={"dateFrom": str(TOMORROW), "dateTo": str(TOMORROW)},
    )
    assert r.status_code == 200, r.text
    assert [(c["room"]["id"], c["hour"]) for c in r.json()["candidates"]] == [("J05", 12)]


def test_school_down_returns_503(real_provider_client, school):
    school.fail = httpx.ConnectError("down")
    r = real_provider_client.get("/api/rooms/availability", params={"date": str(TOMORROW)})
    assert r.status_code == 503 and r.json()["detail"] == MSG_UNAVAILABLE
