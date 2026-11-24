"""로그인한 여러 사용자가 모임을 함께 쓰는 흐름: 이메일 초대(5) · 권한."""

from datetime import timedelta

import pytest

from app.timeutil import today_kst
from tests.conftest import signup

TOMORROW = today_kst() + timedelta(days=1)


@pytest.fixture
def users(client):
    """owner, b, c 세 명이 가입한 상태. 값은 Authorization 헤더."""
    return {
        "owner": signup(client, "owner@example.com", "모임장"),
        "b": signup(client, "b@example.com", "비"),
        "c": signup(client, "c@example.com", "씨"),
    }


def make_group(client, h, names=()):
    r = client.post("/api/groups", json={"name": "캡스톤", "memberNames": list(names)}, headers=h)
    assert r.status_code == 201, r.text
    return r.json()


def invite(client, h, gid, email):
    return client.post(f"/api/groups/{gid}/invites", json={"email": email}, headers=h)


def join(client, users, gid, who):
    """owner가 who를 초대하고 who가 수락한다. who의 팀원 id를 돌려준다."""
    mid = invite(client, users["owner"], gid, f"{who}@example.com").json()["id"]
    assert client.post(f"/api/invites/{mid}/accept", headers=users[who]).status_code == 200
    return mid


def test_login_is_required(client):
    for method, url in [
        ("get", "/api/groups"),
        ("post", "/api/groups"),
        ("get", "/api/groups/x"),
        ("get", "/api/groups/x/availability"),
        ("get", "/api/invites"),
    ]:
        assert getattr(client, method)(url).status_code == 401, url
    r = client.get("/api/rooms/availability", params={"date": str(TOMORROW), "groupId": "x"})
    assert r.status_code == 401
    # 장소·호실 정보와 groupId 없는 호실 현황은 로그인 없이도 볼 수 있다
    assert client.get("/api/places").status_code == 200
    assert client.get("/api/rooms").status_code == 200
    assert client.get("/api/rooms/availability", params={"date": str(TOMORROW)}).status_code == 200


def test_other_users_group_is_invisible(client, users):
    g = make_group(client, users["owner"])
    assert client.get(f"/api/groups/{g['id']}", headers=users["b"]).status_code == 404
    assert client.get(f"/api/groups/{g['id']}/availability", headers=users["b"]).status_code == 404
    assert client.get("/api/groups", headers=users["b"]).json() == []
    r = client.get(
        "/api/rooms/availability",
        params={"date": str(TOMORROW), "groupId": g["id"]},
        headers=users["b"],
    )
    assert r.status_code == 404


def test_email_invite_accept_flow(client, users):
    g = make_group(client, users["owner"], names=["계정없는팀원"])
    gid = g["id"]

    r = invite(client, users["owner"], gid, " B@Example.com ")
    assert r.status_code == 201
    pending = r.json()
    assert (pending["email"], pending["status"], pending["userId"]) == (
        "b@example.com",
        "invited",
        None,
    )
    assert invite(client, users["owner"], gid, "b@example.com").status_code == 409
    assert invite(client, users["owner"], gid, "owner@example.com").status_code == 409
    assert invite(client, users["owner"], gid, "not-email").status_code == 422

    # 대기중인 팀원은 공강 계산에서 빠진다
    avail = client.get(f"/api/groups/{gid}/availability", headers=users["owner"]).json()
    assert avail["total"] == 2

    # b가 로그인해서 자기에게 온 초대를 본다
    inbox = client.get("/api/invites", headers=users["b"]).json()
    assert inbox == [
        {
            "memberId": pending["id"],
            "groupId": gid,
            "groupName": "캡스톤",
            "inviterName": "모임장",
            "memberCount": 2,  # 참여한 사람만 (대기중 제외)
        }
    ]
    assert client.get("/api/invites", headers=users["c"]).json() == []
    # 남의 초대는 수락할 수 없다
    assert (
        client.post(f"/api/invites/{pending['id']}/accept", headers=users["c"]).status_code == 404
    )

    r = client.post(f"/api/invites/{pending['id']}/accept", headers=users["b"])
    assert r.status_code == 200
    b_row = next(m for m in r.json()["members"] if m["id"] == pending["id"])
    assert (b_row["name"], b_row["status"]) == ("비", "joined")
    assert b_row["userId"] == client.get("/api/auth/me", headers=users["b"]).json()["id"]

    assert [x["id"] for x in client.get("/api/groups", headers=users["b"]).json()] == [gid]
    assert client.get("/api/invites", headers=users["b"]).json() == []
    assert (
        client.post(f"/api/invites/{pending['id']}/accept", headers=users["b"]).status_code == 404
    )
    avail = client.get(f"/api/groups/{gid}/availability", headers=users["b"]).json()
    assert avail["total"] == 3


def test_decline_and_cancel_invite(client, users):
    gid = make_group(client, users["owner"])["id"]
    b = invite(client, users["owner"], gid, "b@example.com").json()["id"]
    assert client.post(f"/api/invites/{b}/decline", headers=users["b"]).status_code == 204
    c = invite(client, users["owner"], gid, "c@example.com").json()["id"]
    # 보낸 초대 취소 = 대기중 팀원 삭제
    assert (
        client.delete(f"/api/groups/{gid}/members/{c}", headers=users["owner"]).status_code == 204
    )
    members = client.get(f"/api/groups/{gid}", headers=users["owner"]).json()["members"]
    assert [m["name"] for m in members] == ["모임장"]
    assert client.get("/api/invites", headers=users["c"]).json() == []


def test_invite_before_signup(client):
    owner = signup(client, "owner@example.com", "모임장")
    gid = make_group(client, owner)["id"]
    invite(client, owner, gid, "later@example.com")
    later = signup(client, "LATER@example.com", "나중")
    assert [i["groupId"] for i in client.get("/api/invites", headers=later).json()] == [gid]


def test_member_limit_counts_pending_invites(client, users):
    gid = make_group(client, users["owner"], names=[f"팀원{i}" for i in range(10)])["id"]  # 11명
    assert invite(client, users["owner"], gid, "b@example.com").status_code == 201  # 12명
    assert invite(client, users["owner"], gid, "c@example.com").status_code == 400
    r = client.post(f"/api/groups/{gid}/members", json={"name": "x"}, headers=users["owner"])
    assert r.status_code == 400


def test_member_edit_permissions(client, users):
    g = make_group(client, users["owner"], names=["계정없는팀원"])
    gid = g["id"]
    owner_mid, name_only = g["members"][0]["id"], g["members"][1]["id"]
    b_mid = join(client, users, gid, "b")
    url = f"/api/groups/{gid}/members/"

    # 내 시간표, 계정 없는 팀원 시간표는 고칠 수 있다
    assert client.patch(url + b_mid, json={"busy": ["0-0"]}, headers=users["b"]).status_code == 200
    r = client.patch(url + name_only, json={"busy": ["1-1"]}, headers=users["b"])
    assert r.status_code == 200
    # 다른 계정 팀원 것은 안 된다 (모임장이어도)
    r = client.patch(url + owner_mid, json={"busy": ["0-0"]}, headers=users["b"])
    assert r.status_code == 403 and r.json()["detail"] == "다른 팀원의 정보는 바꿀 수 없어요."
    assert client.patch(url + b_mid, json={"busy": []}, headers=users["owner"]).status_code == 403


def test_nickname_change_updates_member_name(client, users):
    gid = make_group(client, users["owner"])["id"]
    join(client, users, gid, "b")
    client.patch("/api/auth/me", json={"nickname": "새비"}, headers=users["b"])
    names = [
        m["name"]
        for m in client.get(f"/api/groups/{gid}", headers=users["owner"]).json()["members"]
    ]
    assert names == ["모임장", "새비"]


def test_leave_kick_and_delete_permissions(client, users):
    g = make_group(client, users["owner"], names=["계정없는팀원"])
    gid, owner_mid, name_only = g["id"], g["members"][0]["id"], g["members"][1]["id"]
    b_mid = join(client, users, gid, "b")
    c_mid = join(client, users, gid, "c")
    url = f"/api/groups/{gid}/members/"

    # 모임장이 아니면: 모임 삭제·다른 계정 팀원 내보내기 불가, 모임장은 나갈 수 없음
    r = client.delete(f"/api/groups/{gid}", headers=users["b"])
    assert r.status_code == 403 and r.json()["detail"] == "모임을 만든 사람만 삭제할 수 있어요."
    assert client.delete(url + c_mid, headers=users["b"]).status_code == 403
    assert client.delete(url + owner_mid, headers=users["b"]).status_code == 400
    # 계정 없는 팀원은 누구나 뺄 수 있다
    assert client.delete(url + name_only, headers=users["b"]).status_code == 204

    # b가 스스로 나가면 더 이상 모임이 안 보인다
    assert client.delete(url + b_mid, headers=users["b"]).status_code == 204
    assert client.get(f"/api/groups/{gid}", headers=users["b"]).status_code == 404

    # 모임장은 계정 팀원을 내보낼 수 있다
    assert client.delete(url + c_mid, headers=users["owner"]).status_code == 204
    assert client.get("/api/groups", headers=users["c"]).json() == []
    assert client.delete(f"/api/groups/{gid}", headers=users["owner"]).status_code == 204
