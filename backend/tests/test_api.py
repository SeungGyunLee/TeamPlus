"""API 통합 테스트: 모임 → 시간표 → 공강 → 호실 현황 → 예약 → 추천 → 과제 단계."""

from datetime import time, timedelta

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
from app.services.booking import MSG_CAPACITY, MSG_GROUP_CONFLICT, MSG_OCCUPIED, MSG_RANGE
from app.timeutil import today_kst
from tests.conftest import needs_ai_prompts

TOMORROW = today_kst() + timedelta(days=1)


def make_group(client, names=None, name="오픈소스 프로젝트"):
    body = {"name": name} if names is None else {"name": name, "memberNames": names}
    r = client.post("/api/groups", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def set_busy(client, group, member_index, keys):
    m = group["members"][member_index]
    r = client.patch(f"/api/groups/{group['id']}/members/{m['id']}", json={"busy": keys})
    assert r.status_code == 200, r.text
    return r.json()


def book(client, group_id, room="J201", day=TOMORROW, hour=10):
    return client.post(
        "/api/reservations",
        json={"groupId": group_id, "roomId": room, "date": str(day), "hour": hour},
    )


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}


# ---------- 모임·팀원 ----------
def test_create_group_with_frontend_defaults(client):
    g = make_group(client)
    assert [m["name"] for m in g["members"]] == ["짱구", "철수", "훈이"]
    assert all(m["busy"] == [] for m in g["members"])
    # 프론트와 같은 camelCase 필드
    assert {"id", "name", "ownerId", "inviteCode", "members", "updatedAt"} <= set(g)
    assert g["ownerId"] == "local-owner" and len(g["inviteCode"]) == 8


def test_group_needs_at_least_one_member(client):
    assert client.post("/api/groups", json={"memberNames": []}).status_code == 400
    g = make_group(client, names=["혼자"])
    only = g["members"][0]["id"]
    assert client.delete(f"/api/groups/{g['id']}/members/{only}").status_code == 400


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
    assert names == ["짱구", "철수", "훈이"]


def test_list_groups_recent_first_and_invite_lookup(client):
    a = make_group(client, name="A")
    b = make_group(client, name="B")
    client.patch(f"/api/groups/{a['id']}", json={"name": "A2"})
    assert [g["name"] for g in client.get("/api/groups").json()] == ["A2", "B"]
    assert client.get(f"/api/groups/by-invite/{b['inviteCode']}").json()["id"] == b["id"]
    assert client.get("/api/groups/by-invite/nope").status_code == 404
    assert client.get("/api/groups/nope").status_code == 404


def test_member_of_other_group_is_404(client):
    a, b = make_group(client), make_group(client)
    other = b["members"][0]["id"]
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
    assert [(r["id"], r["capacity"]) for r in rooms] == [
        ("J201", 4),
        ("J202", 4),
        ("J301", 6),
        ("J302", 8),
    ]
    assert rooms[0]["fullName"] == "집현전 201호" and rooms[0]["placeId"] == "jiphyeon"


def test_room_slot_states(client, provider):
    g = make_group(client)
    provider.add("J202", TOMORROW, time(13), time(14))
    assert book(client, g["id"], room="J201", hour=10).status_code == 201
    rooms = {
        r["roomId"]: r
        for r in client.get(
            "/api/rooms/availability", params={"date": str(TOMORROW), "groupId": g["id"]}
        ).json()
    }
    j201 = {s["hour"]: s for s in rooms["J201"]["slots"]}
    j202 = {s["hour"]: s for s in rooms["J202"]["slots"]}
    assert len(j201) == 10 and j201[9]["label"] == "09:00–10:00"
    assert j201[10]["state"] == "mine" and not j201[10]["selectable"]
    assert j202[13]["state"] == "occupied"
    assert j202[10]["state"] == "group_conflict"  # 같은 모임이 10시에 201호 예약함
    assert j202[11]["state"] == "available" and j202[11]["selectable"]
    assert rooms["J201"]["fitsGroup"] is True


def test_room_too_small_for_group(client):
    g = make_group(client, names=list("가나다라마"))
    rooms = {
        r["roomId"]: r
        for r in client.get(
            "/api/rooms/availability", params={"date": str(TOMORROW), "groupId": g["id"]}
        ).json()
    }
    assert rooms["J201"]["fitsGroup"] is False
    assert not any(s["selectable"] for s in rooms["J201"]["slots"])
    assert rooms["J301"]["fitsGroup"] is True


# ---------- 예약 ----------
def test_reservation_flow_matches_frontend_rules(client):
    a, b = make_group(client, name="A"), make_group(client, name="B")
    r = book(client, a["id"], room="J201", hour=10)
    assert r.status_code == 201
    res = r.json()
    assert {"id", "groupId", "groupName", "roomId", "date", "hour", "status", "createdAt"} <= set(
        res
    )
    assert (res["groupName"], res["status"]) == ("A", "active")

    assert book(client, b["id"], room="J201", hour=10).json()["detail"] == MSG_OCCUPIED
    assert book(client, a["id"], room="J202", hour=10).json()["detail"] == MSG_GROUP_CONFLICT
    assert book(client, a["id"], day=today_kst() - timedelta(days=1)).json()["detail"] == MSG_RANGE
    assert book(client, a["id"], day=today_kst() + timedelta(days=30)).json()["detail"] == MSG_RANGE
    big = make_group(client, names=list("가나다라마"))
    assert book(client, big["id"], room="J201", hour=11).json()["detail"] == MSG_CAPACITY
    assert book(client, a["id"], room="NOPE").status_code == 400

    # 취소하면 같은 슬롯을 다시 예약할 수 있다
    cancelled = client.post(f"/api/reservations/{res['id']}/cancel").json()
    assert cancelled["status"] == "cancelled"
    assert book(client, b["id"], room="J201", hour=10).status_code == 201

    mine = client.get("/api/reservations", params={"groupId": a["id"]}).json()
    assert [x["status"] for x in mine] == ["cancelled"]
    assert len(client.get("/api/reservations", params={"status": "active"}).json()) == 1


def test_seed_occupied_slot_cannot_be_booked(client):
    app.dependency_overrides[deps.get_provider] = lambda: SeedReservationProvider()
    g = make_group(client)
    day = TOMORROW
    room, hour = next(
        (r, h)
        for d in range(1, 10)
        for r in ("J201", "J202", "J301", "J302")
        for h in range(9, 19)
        if seed_occupied(r, (day := today_kst() + timedelta(days=d)), h)
    )
    r = book(client, g["id"], room=room, day=day, hour=hour)
    assert r.json()["detail"] == MSG_OCCUPIED


def test_delete_group_cancels_its_reservations(client):
    g = make_group(client, name="지울 모임")
    rid = book(client, g["id"]).json()["id"]
    assert client.delete(f"/api/groups/{g['id']}").status_code == 204
    assert client.get(f"/api/groups/{g['id']}").status_code == 404
    kept = client.get("/api/reservations").json()
    assert [(x["id"], x["status"], x["groupName"]) for x in kept] == [
        (rid, "cancelled", "지울 모임")
    ]


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
    # 추천 결과의 roomId·date·hour로 바로 예약할 수 있다
    assert (
        book(client, g["id"], room=c["room"]["id"], day=TOMORROW, hour=c["hour"]).status_code == 201
    )


def test_recommendation_date_window(client):
    g = make_group(client)
    past = str(today_kst() - timedelta(days=1))
    r = client.post(
        f"/api/groups/{g['id']}/recommendations", json={"dateFrom": past, "dateTo": past}
    )
    assert r.status_code == 422


@needs_ai_prompts
def test_full_recommendation_flow(client, fake_llm, provider):
    g = make_group(client)
    # 철수: 수요일 5교시(15:00~16:30) 수업
    wed = TOMORROW
    while wed.weekday() != 2:
        wed += timedelta(days=1)
    set_busy(client, g, 2, ["2-4"])

    fake_llm.set(
        ParsedConditions,
        conditions(
            capacity=3, needs_outlet=True, room_type="study_room", time_preference="수요일 3시 이후"
        ),
    )
    cond = client.post(f"/api/groups/{g['id']}/conditions", json={"text": "수요일 3시 이후"}).json()
    assert cond["type"] == "conditions"
    assert cond["conditions"]["needsOutlet"] is True  # camelCase

    # 201호는 17시 점유, 이 모임은 18시에 이미 302호 예약
    provider.add("J201", wed, time(17), time(18))
    assert book(client, g["id"], room="J302", day=wed, hour=18).status_code == 201
    fake_llm.set(
        RecommendationReasons,
        RecommendationReasons(
            recommendations=[Recommendation(candidate_id="C01", reason="AI 설명")]
        ),
    )
    rec = client.post(
        f"/api/groups/{g['id']}/recommendations",
        json={"conditions": cond["conditions"], "dateFrom": str(wed), "dateTo": str(wed)},
    ).json()

    assert rec["timePreferenceApplied"] is True
    hours = [(c["room"]["id"], c["hour"]) for c in rec["candidates"]]
    assert all(h >= 15 for _, h in hours)
    assert ("J201", 17) not in hours
    assert all(h != 18 for _, h in hours)  # 같은 모임 예약 시간 제외
    assert rec["excludedWindows"]["groupConflict"] >= 1
    first = rec["candidates"][0]
    # 15·16시는 철수 수업(15:00~16:30)과 겹침 → 17시가 첫 초록. 콘센트 있는 4인실 중 202호
    assert (first["status"], first["hour"], first["room"]["id"]) == ("green", 17, "J202")
    assert first["reason"] == "AI 설명"
    assert rec["reasonsSource"] == "partial"
    assert '"place_name": "집현전 202호"' in fake_llm.calls[-1]["system"]


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
