"""메일 발송: 비밀번호 찾기(인증 코드), 모임 초대 메일."""

import re
from datetime import timedelta

import pytest

from app.db import SessionLocal
from app.models import PasswordReset
from app.services import mail as mail_service
from app.services.mail import SmtpMailer, build_mailer, invite_mail, send_safely
from app.timeutil import now_kst
from tests.conftest import signup

REQUEST = "/api/auth/password-reset/request"
CONFIRM = "/api/auth/password-reset/confirm"


def code_in(mail) -> str:
    return re.search(r"인증 코드: (\d{6})", mail.body).group(1)


def confirm(client, code, password="newpassword1", email="me@example.com"):
    return client.post(CONFIRM, json={"email": email, "code": code, "newPassword": password})


# ---------- 비밀번호 찾기 ----------
def test_password_reset_flow(client, mailer):
    old = signup(client, "me@example.com", password="password123")

    r = client.post(REQUEST, json={"email": " ME@example.com "})
    assert r.status_code == 202
    assert "인증 코드를 보냈어요" in r.json()["message"]
    [sent] = mailer.sent
    assert sent.to == "me@example.com" and "비밀번호 재설정" in sent.subject
    code = code_in(sent)

    r = confirm(client, code, "newpassword1")
    assert r.status_code == 200 and r.json()["accessToken"]
    # 예전 로그인은 끊기고, 예전 비밀번호로는 로그인 안 됨
    assert client.get("/api/auth/me", headers=old).status_code == 401
    login = client.post(
        "/api/auth/login", json={"email": "me@example.com", "password": "password123"}
    )
    assert login.status_code == 401
    login = client.post(
        "/api/auth/login", json={"email": "me@example.com", "password": "newpassword1"}
    )
    assert login.status_code == 200
    # 한 번 쓴 코드는 다시 못 씀
    assert confirm(client, code).status_code == 400


def test_unknown_email_gets_same_answer_and_no_mail(client, mailer):
    r = client.post(REQUEST, json={"email": "nobody@example.com"})
    assert r.status_code == 202 and "인증 코드를 보냈어요" in r.json()["message"]
    assert mailer.sent == []
    assert confirm(client, "123456", email="nobody@example.com").status_code == 400
    assert client.post(REQUEST, json={"email": "not-email"}).status_code == 422


def test_resend_waits_one_minute(client, mailer):
    signup(client)
    client.post(REQUEST, json={"email": "me@example.com"})
    client.post(REQUEST, json={"email": "me@example.com"})
    assert len(mailer.sent) == 1  # 1분 안에 다시 눌러도 메일은 한 번

    with SessionLocal() as db:  # 1분이 지난 것으로
        row = db.query(PasswordReset).one()
        row.created_at = now_kst() - timedelta(seconds=61)
        db.commit()
    client.post(REQUEST, json={"email": "me@example.com"})
    assert len(mailer.sent) == 2
    first, second = (code_in(m) for m in mailer.sent)
    if first != second:  # 새 코드가 나가면 예전 코드는 못 씀
        assert confirm(client, first).status_code == 400
    assert confirm(client, second).status_code == 200


def test_wrong_code_five_times_locks(client, mailer):
    signup(client)
    client.post(REQUEST, json={"email": "me@example.com"})
    code = code_in(mailer.sent[0])
    wrong = "000000" if code != "000000" else "111111"
    for _ in range(4):
        assert confirm(client, wrong).json()["detail"] == "인증 코드가 맞지 않거나 만료됐어요."
    assert "여러 번 틀렸어요" in confirm(client, wrong).json()["detail"]
    assert confirm(client, code).status_code == 400  # 맞는 코드여도 잠김


def test_expired_code(client, mailer):
    signup(client)
    client.post(REQUEST, json={"email": "me@example.com"})
    with SessionLocal() as db:
        row = db.query(PasswordReset).one()
        row.expires_at = now_kst() - timedelta(seconds=1)
        db.commit()
    assert confirm(client, code_in(mailer.sent[0])).status_code == 400


def test_confirm_validation(client, mailer):
    signup(client)
    client.post(REQUEST, json={"email": "me@example.com"})
    code = code_in(mailer.sent[0])
    body = {"email": "me@example.com", "code": code, "newPassword": "newpassword1"}
    assert client.post(CONFIRM, json={**body, "code": "12ab56"}).status_code == 422
    assert client.post(CONFIRM, json={**body, "newPassword": "short"}).status_code == 422
    r = client.post(CONFIRM, json={**body, "newPasswordConfirm": "different1"})
    assert r.status_code == 400 and r.json()["detail"] == "비밀번호가 서로 달라요."
    assert client.post(CONFIRM, json=body).status_code == 200  # 위 실패들은 횟수에 안 셈


def test_code_is_not_stored_in_plain_text(client, mailer):
    signup(client)
    client.post(REQUEST, json={"email": "me@example.com"})
    with SessionLocal() as db:
        assert code_in(mailer.sent[0]) not in db.query(PasswordReset).one().code_hash


# ---------- 초대 메일 ----------
def test_invite_sends_mail_with_inviter_and_group(client, mailer):
    owner = signup(client, "owner@example.com", "모임장")
    signup(client, "member@example.com", "팀원")
    g = client.post("/api/groups", json={"name": "캡스톤"}, headers=owner).json()

    client.post(
        f"/api/groups/{g['id']}/invites", json={"email": "member@example.com"}, headers=owner
    )
    client.post(f"/api/groups/{g['id']}/invites", json={"email": "new@example.com"}, headers=owner)
    to_member, to_new = mailer.sent
    assert to_member.to == "member@example.com"
    assert to_member.subject == "[KW Meet] 모임장님이 '캡스톤' 모임에 초대했어요"
    assert "로그인하면" in to_member.body  # 이미 가입한 사람
    assert to_new.to == "new@example.com" and "가입하면" in to_new.body

    # 실패한 초대(중복)는 메일을 보내지 않음
    client.post(f"/api/groups/{g['id']}/invites", json={"email": "new@example.com"}, headers=owner)
    assert len(mailer.sent) == 2


def test_user_input_cannot_break_mail_subject():
    m = invite_mail("a@example.com", "나쁜\r\nBcc: x@example.com", "모임\n이름", True)
    assert "\n" not in m.subject and "\r" not in m.subject


# ---------- 발송기 ----------
def test_failed_send_does_not_raise(caplog):
    class Broken:
        def send(self, mail):
            raise OSError("smtp down")

    send_safely(Broken(), invite_mail("a@example.com", "나", "모임", True))
    assert "메일 발송 실패" in caplog.text and "a@example.com" not in caplog.text


def test_build_mailer_config_errors():
    assert build_mailer("console").__class__.__name__ == "ConsoleMailer"
    with pytest.raises(ValueError, match="SMTP_HOST"):
        build_mailer("smtp")
    with pytest.raises(ValueError, match="MAIL_BACKEND"):
        build_mailer("pigeon")
    with pytest.raises(ValueError, match="SMTP_SECURITY"):
        build_mailer("smtp", host="h", sender="a@example.com", security="tls1")


class FakeSMTP:
    instances: list["FakeSMTP"] = []

    def __init__(self, host, port, timeout=None, context=None):
        self.host, self.port, self.calls = host, port, []
        FakeSMTP.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.calls.append("quit")

    def starttls(self, context=None):
        self.calls.append("starttls")

    def login(self, user, password):
        self.calls.append(("login", user, password))

    def send_message(self, msg):
        self.calls.append(("send", msg["From"], msg["To"], msg["Subject"], msg.get_content()))


@pytest.mark.parametrize(("security", "uses_ssl_class"), [("starttls", False), ("ssl", True)])
def test_smtp_mailer(monkeypatch, security, uses_ssl_class):
    FakeSMTP.instances = []
    monkeypatch.setattr(mail_service.smtplib, "SMTP", FakeSMTP)
    monkeypatch.setattr(mail_service.smtplib, "SMTP_SSL", FakeSMTP)
    mailer = SmtpMailer(
        "smtp.example.com", 465 if uses_ssl_class else 587, "bot@example.com", "pw",
        "bot@example.com", security=security,
    )  # fmt: skip
    mailer.send(invite_mail("to@example.com", "나", "모임", False))
    [smtp] = FakeSMTP.instances
    assert ("starttls" in smtp.calls) is (security == "starttls")
    assert ("login", "bot@example.com", "pw") in smtp.calls
    sent = next(c for c in smtp.calls if c[0] == "send")
    assert sent[1] == "KW Meet <bot@example.com>" and sent[2] == "to@example.com"
    assert "모임" in sent[3] and "가입하면" in sent[4]
