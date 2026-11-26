"""API 통합 테스트: 모임 → 시간표 → 공강 → 호실 현황 → 추천 → 과제 단계."""

from datetime import time, timedelta

import pytest

from app import deps
from app.ai.client import LLMError
from app.ai.schemas import (
    AssignmentAnalysis,
    MeetingStage,
    Milestone,
    ParsedConditions,
    Recommendation,
    RecommendationReasons,
)
from app.main import app
from app.places.provider import SeedReservationProvider, seed_occupied
from app.services.booking import MSG_WINDOW
from app.timeutil import today_kst
from tests.conftest import needs_ai_prompts, signup

TOMORROW = today_kst() + timedelta(days=1)


@pytest.fixture(autouse=True)
def _logged_in(client):
    """이 파일의 요청은 모두 '나'(me@example.com)로 로그인한 상태에서 보낸다."""
    client.headers.update(signup(client, nickname="나"))


def make_group(client, names=("짱구", "철수"), name="오픈소스 프로젝트"):
    """만든 사람('나')이 자동으로 첫 번째 팀원이 되고, names는 계정 없는 팀원으로 들어간다."""
    r = client.post("/api/groups", json={"name": name, "memberNames": list(names)})
    assert r.status_code == 201, r.text
    return r.json()


def set_busy(client, group, member_index, keys):
    m = group["members"][member_index]
    r = client.patch(f"/api/groups/{group['id']}/members/{m['id']}", json={"busy": keys})
    assert r.status_code == 200, r.text
    return r.json()


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}


# ---------- 모임·팀원 ----------
def test_create_group_creator_joins_automatically(client):
    me = client.get("/api/auth/me").json()
    g = make_group(client)
    assert [m["name"] for m in g["members"]] == ["나", "짱구", "철수"]
    first = g["members"][0]
    assert (first["userId"], first["email"], first["status"]) == (me["id"], me["email"], "joined")
    assert all(m["userId"] is None and m["status"] == "joined" for m in g["members"][1:])
    assert all(m["busy"] == [] for m in g["members"])
    # 프론트와 같은 camelCase 필드
    assert {"id", "name", "ownerId", "inviteCode", "members", "updatedAt"} <= set(g)
    assert g["ownerId"] == me["id"] and g["inviteCode"] is None

    alone = client.post("/api/groups", json={}).json()
    assert alone["name"] == "새로운 모임" and [m["name"] for m in alone["members"]] == ["나"]


def test_owner_cannot_leave_own_group(client):
    g = make_group(client, names=[])
    me = g["members"][0]["id"]
    r = client.delete(f"/api/groups/{g['id']}/members/{me}")
    assert r.status_code == 400 and "삭제" in r.json()["detail"]


def test_rename_edit_members_and_order(client):
    g = make_group(client)
    gid = g["id"]
    r = client.patch(f"/api/groups/{gid}", json={"name": "새 이름"})
    assert r.json()["name"] == "새 이름" and r.json()["updatedAt"] >= g["updatedAt"]

    new = client.post(f"/api/groups/{gid}/members", json={"name": "민서"}).json()
    member = set_busy(client, client.get(f"/api/groups/{gid}").json(), 3, ["1-2", "0-0", "0-0"])
    assert member["id"] == new["id"]
    assert member["busy"] == ["0-0", "1-2"]  # 중복 제거·정렬
    r = client.patch(f"/api/groups/{gid}/members/{new['id']}", json={"name": "민서2"})
    assert r.json()["name"] == "민서2" and r.json()["busy"] == ["0-0", "1-2"]

    bad = client.patch(f"/api/groups/{gid}/members/{new['id']}", json={"busy": ["5-0"]})
    assert bad.status_code == 422

    assert client.delete(f"/api/groups/{gid}/members/{new['id']}").status_code == 204
    names = [m["name"] for m in client.get(f"/api/groups/{gid}").json()["members"]]
    assert names == ["나", "짱구", "철수"]


def test_list_groups_recent_first(client):
    a = make_group(client, name="A")
    make_group(client, name="B")
    client.patch(f"/api/groups/{a['id']}", json={"name": "A2"})
    assert [g["name"] for g in client.get("/api/groups").json()] == ["A2", "B"]
    assert client.get("/api/groups/nope").status_code == 404


def test_member_of_other_group_is_404(client):
    a, b = make_group(client), make_group(client)
    other = b["members"][1]["id"]
    assert (
        client.patch(f"/api/groups/{a['id']}/members/{other}", json={"name": "x"}).status_code
        == 404
    )


# ---------- 공강 ----------
def test_availability_thirty_blocks_ranked(client):
    g = make_group(client)
    set_busy(client, g, 0, ["0-0", "2-3"])
    set_busy(client, g, 1, ["0-0"])
    r = client.get(f"/api/groups/{g['id']}/availability").json()
    assert r["total"] == 3 and len(r["blocks"]) == 30
    assert r["fullCount"] == 28
    first, last = r["blocks"][0], r["blocks"][-1]
    assert (first["key"], first["level"], first["periodLabel"]) == ("0-1", "full", "10:30–12:00")
    assert (last["key"], last["count"], last["level"]) == ("0-0", 1, "partial")
    ids = [m["id"] for m in g["members"]]
    assert last["availableMemberIds"] == [ids[2]]
    assert last["unavailableMemberIds"] == ids[:2]


# ---------- 장소·호실 ----------
def test_places_and_rooms(client):
    places = client.get("/api/places").json()
    assert [p["id"] for p in places] == ["jiphyeon", "reading", "cafe"]
    assert client.get("/api/places/jiphyeon").json()["reservable"] is True
    assert client.get("/api/places/nope").status_code == 404
    rooms = client.get("/api/rooms").json()
    # 실제 집현전 그룹학습실 (10·11실은 학교 API로 현황을 알 수 없어 제외)
    assert [(r["id"], r["capacity"]) for r in rooms] == [
        ("J01", 10),
        ("J02", 6),
        ("J03", 6),
        ("J04", 4),
        ("J05", 4),
        ("J06", 4),
        ("J07", 4),
        ("J08", 4),
        ("J09", 4),
        ("J12", 6),
        ("J13", 10),
    ]
    assert rooms[3]["fullName"] == "집현전 4실" and rooms[3]["placeId"] == "jiphyeon"
    assert all(r["hasOutlet"] and r["laptopSpace"] for r in rooms)


def test_room_slot_states(client, provider):
    g = make_group(client)
    provider.add("J05", TOMORROW, time(13), time(14))
    rooms = {
        r["roomId"]: r
        for r in client.get(
            "/api/rooms/availability", params={"date": str(TOMORROW), "groupId": g["id"]}
        ).json()
    }
    j04 = {s["hour"]: s for s in rooms["J04"]["slots"]}
    j05 = {s["hour"]: s for s in rooms["J05"]["slots"]}
    assert len(j04) == 10 and j04[9]["label"] == "09:00–10:00"
    assert j05[13]["state"] == "occupied" and not j05[13]["selectable"]
    assert j05[11]["state"] == "available" and j05[11]["selectable"]
    assert {s["state"] for s in j04.values()} == {"available"}
    assert rooms["J04"]["fitsGroup"] is True


def test_room_availability_only_for_next_seven_days(client):
    today = today_kst()
    ok = client.get("/api/rooms/availability", params={"date": str(today + timedelta(days=6))})
    assert ok.status_code == 200
    for day in (today - timedelta(days=1), today + timedelta(days=7)):
        r = client.get("/api/rooms/availability", params={"date": str(day)})
        assert r.status_code == 422 and r.json()["detail"] == MSG_WINDOW


def test_room_too_small_for_group(client):
    g = make_group(client, names=list("가나다라마"))  # 나 + 5명 = 6명
    rooms = {
        r["roomId"]: r
        for r in client.get(
            "/api/rooms/availability", params={"date": str(TOMORROW), "groupId": g["id"]}
        ).json()
    }
    assert rooms["J04"]["fitsGroup"] is False  # 4인실
    assert not any(s["selectable"] for s in rooms["J04"]["slots"])
    assert rooms["J02"]["fitsGroup"] is True  # 6인실


def test_seed_occupied_slot_shows_as_occupied(client):
    app.dependency_overrides[deps.get_provider] = lambda: SeedReservationProvider()
    room, day, hour = next(
        (r, day, h)
        for d in range(1, 7)
        for r in ("J01", "J04", "J05", "J12")
        for h in range(9, 19)
        if seed_occupied(r, (day := today_kst() + timedelta(days=d)), h)
    )
    rooms = client.get("/api/rooms/availability", params={"date": str(day)}).json()
    slots = {s["hour"]: s["state"] for s in next(x for x in rooms if x["roomId"] == room)["slots"]}
    assert slots[hour] == "occupied"


def test_virtual_reservation_api_is_gone(client):
    # 실제 예약은 중앙도서관 앱에서 한다 (팀 결정)
    assert client.get("/api/reservations").status_code == 404
    g = make_group(client, name="지울 모임")
    assert client.delete(f"/api/groups/{g['id']}").status_code == 204
    assert client.get(f"/api/groups/{g['id']}").status_code == 404


# ---------- 추천 ----------
def conditions(**kw):
    base = dict(
        capacity=None,
        noise_level="무관",
        needs_outlet=None,
        needs_laptop_space=None,
        room_type="무관",
        time_preference=None,
        clarifying_question=None,
    )
    base.update(kw)
    return ParsedConditions(**base)


def test_recommendation_without_ai_uses_fallback_reasons(client):
    app.dependency_overrides[deps.get_llm] = lambda: None
    g = make_group(client)
    r = client.post(
        f"/api/groups/{g['id']}/recommendations",
        json={"dateFrom": str(TOMORROW), "dateTo": str(TOMORROW), "limit": 3},
    ).json()
    assert r["reasonsSource"] == "fallback"
    assert len(r["candidates"]) == 3
    c = r["candidates"][0]
    assert c["status"] == "green" and c["reason"]
    assert c["label"] == f"{c['hour']:02d}:00–{c['hour'] + 1:02d}:00"
    assert c["room"]["id"].startswith("J")


def test_recommendation_date_window_is_clamped_to_seven_days(client):
    app.dependency_overrides[deps.get_llm] = lambda: None
    g = make_group(client)
    today = today_kst()
    url = f"/api/groups/{g['id']}/recommendations"

    # 과제 단계 기간처럼 지난 날짜부터 한 달 뒤까지 걸쳐 와도 오늘~6일 뒤만 찾아본다
    r = client.post(
        url,
        json={
            "dateFrom": str(today - timedelta(days=3)),
            "dateTo": str(today + timedelta(days=30)),
            "limit": 20,
        },
    ).json()
    assert (r["dateFrom"], r["dateTo"]) == (str(today), str(today + timedelta(days=6)))
    assert all(r["dateFrom"] <= c["date"] <= r["dateTo"] for c in r["candidates"])

    # 기간 전체가 7일 밖이면 422
    for a, b in ((-5, -1), (7, 20)):
        r = client.post(
            url,
            json={
                "dateFrom": str(today + timedelta(days=a)),
                "dateTo": str(today + timedelta(days=b)),
            },
        )
        assert r.status_code == 422 and r.json()["detail"] == MSG_WINDOW
    bad = client.post(url, json={"dateFrom": str(today + timedelta(days=2)), "dateTo": str(today)})
    assert bad.status_code == 422


@needs_ai_prompts
def test_full_recommendation_flow(client, fake_llm, provider):
    g = make_group(client)
    # 7일 안의 평일 하루. 세 번째 팀원(철수)은 그날 5교시(15:00~16:30) 수업
    day = next(d for d in (today_kst() + timedelta(days=i) for i in range(1, 7)) if d.weekday() < 5)
    set_busy(client, g, 2, [f"{day.weekday()}-4"])

    fake_llm.set(
        ParsedConditions,
        conditions(
            capacity=3, needs_outlet=True, room_type="study_room", time_preference="오후 3시 이후"
        ),
    )
    cond = client.post(f"/api/groups/{g['id']}/conditions", json={"text": "오후 3시 이후"}).json()
    assert cond["type"] == "conditions"
    assert cond["conditions"]["needsOutlet"] is True  # camelCase

    # 4실은 17시에 도서관 예약이 있음
    provider.add("J04", day, time(17), time(18))
    fake_llm.set(
        RecommendationReasons,
        RecommendationReasons(
            recommendations=[Recommendation(candidate_id="C01", reason="AI 설명")]
        ),
    )
    rec = client.post(
        f"/api/groups/{g['id']}/recommendations",
        json={"conditions": cond["conditions"], "dateFrom": str(day), "dateTo": str(day)},
    ).json()

    assert rec["timePreferenceApplied"] is True
    hours = [(c["room"]["id"], c["hour"]) for c in rec["candidates"]]
    assert all(h >= 15 for _, h in hours)
    assert ("J04", 17) not in hours
    assert rec["excludedWindows"]["booked"] >= 1
    first = rec["candidates"][0]
    # 15·16시는 철수 수업(15:00~16:30)과 겹침 → 17시가 첫 초록.
    # 인원(3명)에 가장 딱 맞는 4인실 중 비어 있는 첫 방 = 5실
    assert (first["status"], first["hour"], first["room"]["id"]) == ("green", 17, "J05")
    assert first["reason"] == "AI 설명"
    assert rec["reasonsSource"] == "partial"
    assert '"place_name": "집현전 5실"' in fake_llm.calls[-1]["system"]


@needs_ai_prompts
def test_conditions_question(client, fake_llm):
    g = make_group(client)
    fake_llm.set(ParsedConditions, conditions(clarifying_question="몇 명이 사용할 예정인가요?"))
    r = client.post(f"/api/groups/{g['id']}/conditions", json={"text": "조용한 데"}).json()
    assert r["type"] == "question" and r["question"] == "몇 명이 사용할 예정인가요?"


def test_conditions_llm_error_and_no_key(client, fake_llm):
    g = make_group(client)
    fake_llm.error = LLMError("boom")
    assert client.post(f"/api/groups/{g['id']}/conditions", json={"text": "x"}).status_code == 502
    app.dependency_overrides[deps.get_llm] = lambda: None
    assert client.post(f"/api/groups/{g['id']}/conditions", json={"text": "x"}).status_code == 503


# ---------- 과제·회의 단계 ----------
def _analysis(deadline, milestone_date):
    return AssignmentAnalysis(
        final_deadline=deadline,
        milestones=[Milestone(name="중간발표", date=milestone_date)],
        deliverable_type="presentation",
        meeting_stages=[
            MeetingStage(name="주제 확정", purpose="주제와 역할 정하기", priority="must"),
            MeetingStage(name="자료조사 공유", purpose="자료 공유", priority="must"),
            MeetingStage(name="중간점검", purpose="중간발표 준비", priority="must"),
            MeetingStage(name="리허설", purpose="최종 발표 연습", priority="optional"),
        ],
    )


@needs_ai_prompts
def test_assignment_flow(client, fake_llm):
    g = make_group(client)
    today = today_kst()
    deadline, mid = today + timedelta(days=30), today + timedelta(days=15)
    fake_llm.set(AssignmentAnalysis, _analysis(deadline, mid))
    base = f"/api/groups/{g['id']}/assignments"

    r = client.post(base, json={"noticeText": "중간발표와 최종발표가 있습니다."})
    assert r.status_code == 201
    a = r.json()
    assert fake_llm.calls[-1]["system"].endswith(f"오늘 날짜: {today.isoformat()}")
    assert a["deadlineSource"] == "ai" and a["deadlineStatus"] == "ok"
    mid_stage = next(s for s in a["stages"] if s["name"] == "중간점검")
    assert mid_stage["anchoredTo"] == "중간발표"
    assert mid_stage["windowEnd"] == str(mid - timedelta(days=1))

    r = client.put(f"{base}/{a['id']}/deadline", json={"finalDeadline": str(today)}).json()
    assert r["deadlineStatus"] == "past" and all(s["windowStart"] is None for s in r["stages"])
    assert len(client.get(base).json()) == 1


@needs_ai_prompts
def test_assignment_missing_and_user_deadline(client, fake_llm):
    g = make_group(client)
    fake_llm.set(AssignmentAnalysis, _analysis(None, None))
    base = f"/api/groups/{g['id']}/assignments"
    a = client.post(base, json={"noticeText": "공지"}).json()
    assert a["deadlineStatus"] == "missing"
    mine = str(today_kst() + timedelta(days=20))
    a = client.post(base, json={"noticeText": "공지", "finalDeadline": mine}).json()
    assert a["finalDeadline"] == mine and a["deadlineSource"] == "user"
