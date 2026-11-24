"""로그인 테스트 (와이어프레임 1~3B)."""

from datetime import timedelta

from app.db import SessionLocal
from app.models import AuthToken, User
from app.services.auth import hash_password, token_hash, verify_password
from app.timeutil import now_kst
from tests.conftest import signup


def test_email_check_then_signup_then_login(client):
    r = client.post("/api/auth/check-email", json={"email": " Me@Example.com "}).json()
    assert r == {"email": "me@example.com", "exists": False}  # 3B 회원가입으로

    r = client.post(
        "/api/auth/signup",
        json={
            "email": "Me@Example.com",
            "password": "password123",
            "passwordConfirm": "password123",
            "nickname": "민수",
        },
    )
    assert r.status_code == 201
    body = r.json()
    assert body["tokenType"] == "bearer" and len(body["accessToken"]) > 20
    assert body["user"]["email"] == "me@example.com" and body["user"]["nickname"] == "민수"
    # 응답 시각은 모두 시간대 포함 (SQLite에서 읽어도)
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {body['accessToken']}"})
    assert me.json()["createdAt"].endswith("+09:00") and body["expiresAt"].endswith("+09:00")

    assert client.post("/api/auth/check-email", json={"email": "me@example.com"}).json()["exists"]

    r = client.post("/api/auth/login", json={"email": "ME@example.com", "password": "password123"})
    assert r.status_code == 200 and r.json()["user"]["id"] == body["user"]["id"]


def test_signup_validation(client):
    signup(client, "dup@example.com")
    ok = {"email": "new@example.com", "password": "password123", "nickname": "a"}
    assert (
        client.post("/api/auth/signup", json={**ok, "email": "dup@example.com"}).status_code == 409
    )
    assert client.post("/api/auth/signup", json={**ok, "email": "not-an-email"}).status_code == 422
    assert client.post("/api/auth/signup", json={**ok, "password": "short"}).status_code == 422
    assert client.post("/api/auth/signup", json={**ok, "nickname": ""}).status_code == 422
    r = client.post("/api/auth/signup", json={**ok, "passwordConfirm": "different1"})
    assert r.status_code == 400 and r.json()["detail"] == "비밀번호가 서로 달라요."
    assert client.post("/api/auth/check-email", json={"email": "bad"}).status_code == 422


def test_login_failures_do_not_reveal_which_part_is_wrong(client):
    signup(client, "me@example.com", password="password123")
    wrong_pw = client.post(
        "/api/auth/login", json={"email": "me@example.com", "password": "nope12345"}
    )
    no_user = client.post("/api/auth/login", json={"email": "who@example.com", "password": "x"})
    assert wrong_pw.status_code == no_user.status_code == 401
    assert (
        wrong_pw.json()["detail"]
        == no_user.json()["detail"]
        == "이메일 또는 비밀번호가 맞지 않아요."
    )


def test_me_requires_valid_token(client):
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/auth/me", headers={"Authorization": "Bearer nope"}).status_code == 401
    h = signup(client, nickname="지수")
    assert client.get("/api/auth/me", headers=h).json()["nickname"] == "지수"
    r = client.patch("/api/auth/me", headers=h, json={"nickname": "새닉네임"})
    assert r.json()["nickname"] == "새닉네임"


def test_logout_invalidates_token(client):
    h = signup(client)
    assert client.post("/api/auth/logout", headers=h).status_code == 204
    assert client.get("/api/auth/me", headers=h).status_code == 401


def test_expired_token_is_rejected(client):
    h = signup(client)
    token = h["Authorization"].split()[1]
    with SessionLocal() as db:
        row = db.get(AuthToken, token_hash(token))
        row.expires_at = now_kst() - timedelta(minutes=1)
        db.commit()
    assert client.get("/api/auth/me", headers=h).status_code == 401


def test_password_is_stored_hashed(client):
    signup(client, "me@example.com", password="password123")
    with SessionLocal() as db:
        user = db.query(User).one()
        assert "password123" not in user.password_hash
        assert user.password_hash.startswith("scrypt$")
    stored = hash_password("abc12345")
    assert verify_password("abc12345", stored)
    assert not verify_password("abc12346", stored)
    assert not verify_password("abc12345", "garbage")
    assert hash_password("abc12345") != stored  # 매번 다른 salt
