"""메일 발송: 비밀번호 재설정 인증 코드, 모임 초대 알림.

MAIL_BACKEND
- console (기본): 실제로 보내지 않고 서버 로그에 메일 내용을 찍는다. 개발·시연용
- smtp: SMTP 서버로 보낸다 (Gmail·네이버 등). 계정·비밀번호는 backend/.env에만 둔다.

메일은 응답을 돌려준 뒤 백그라운드에서 보낸다. 보내다 실패해도 API는 실패하지 않고 로그만 남긴다.
"""

import logging
import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formataddr
from typing import Protocol

log = logging.getLogger(__name__)

APP_NAME = "KW Meet"


@dataclass(frozen=True)
class Mail:
    to: str
    subject: str
    body: str


class Mailer(Protocol):
    def send(self, mail: Mail) -> None: ...


class ConsoleMailer:
    """보내지 않고 서버 로그에 찍는다 (SMTP 설정 전 개발·시연용)"""

    def send(self, mail: Mail) -> None:
        log.warning(
            "[메일 미발송 · MAIL_BACKEND=console]\n받는 사람: %s\n제목: %s\n\n%s",
            mail.to,
            mail.subject,
            mail.body,
        )


class MemoryMailer:
    """보낸 메일을 목록에 모아둔다 (테스트용)"""

    def __init__(self) -> None:
        self.sent: list[Mail] = []

    def send(self, mail: Mail) -> None:
        self.sent.append(mail)


class SmtpMailer:
    def __init__(
        self,
        host: str,
        port: int,
        username: str | None,
        password: str | None,
        sender: str,
        *,
        security: str = "starttls",
        timeout: float = 10.0,
    ):
        if security not in ("starttls", "ssl", "none"):
            raise ValueError(f"SMTP_SECURITY는 starttls | ssl | none 중 하나예요: {security}")
        self.host, self.port = host, port
        self.username, self.password = username, password
        self.sender, self.security, self.timeout = sender, security, timeout

    def send(self, mail: Mail) -> None:
        msg = EmailMessage()
        msg["From"] = formataddr((APP_NAME, self.sender))
        msg["To"] = mail.to
        msg["Subject"] = mail.subject
        msg.set_content(mail.body)

        context = ssl.create_default_context()
        if self.security == "ssl":
            server = smtplib.SMTP_SSL(self.host, self.port, timeout=self.timeout, context=context)
        else:
            server = smtplib.SMTP(self.host, self.port, timeout=self.timeout)
        with server:
            if self.security == "starttls":
                server.starttls(context=context)
            if self.username:
                server.login(self.username, self.password or "")
            server.send_message(msg)


def build_mailer(
    backend: str,
    *,
    host: str | None = None,
    port: int = 587,
    username: str | None = None,
    password: str | None = None,
    sender: str | None = None,
    security: str = "starttls",
) -> Mailer:
    if backend == "console":
        return ConsoleMailer()
    if backend == "smtp":
        if not host or not (sender or username):
            raise ValueError(
                "MAIL_BACKEND=smtp에는 SMTP_HOST와 MAIL_FROM(또는 SMTP_USERNAME)이 필요해요."
            )
        return SmtpMailer(host, port, username, password, sender or username, security=security)
    raise ValueError(f"알 수 없는 MAIL_BACKEND: {backend}")


def send_safely(mailer: Mailer, mail: Mail) -> None:
    """백그라운드 작업용. 실패해도 예외를 밖으로 내보내지 않는다 (받는 주소는 로그에 남기지 않음)"""
    try:
        mailer.send(mail)
    except Exception as e:  # SMTP 오류 종류가 다양해서 전부 잡는다
        log.error("메일 발송 실패 (%s): %s", e.__class__.__name__, mail.subject)


# ---------- 메일 내용 ----------
def _one_line(text: str) -> str:
    """사용자가 입력한 값(모임 이름·닉네임)이 제목 줄을 깨뜨리지 않게 줄바꿈 제거"""
    return " ".join(text.split())


def password_reset_mail(to: str, code: str, minutes: int) -> Mail:
    return Mail(
        to=to,
        subject=f"[{APP_NAME}] 비밀번호 재설정 인증 코드",
        body=(
            f"안녕하세요, {APP_NAME}입니다.\n\n"
            f"비밀번호 재설정 인증 코드: {code}\n\n"
            "앱의 비밀번호 재설정 화면에 위 6자리 코드를 입력해 주세요.\n"
            f"코드는 {minutes}분 동안만 쓸 수 있어요.\n\n"
            "직접 요청하지 않았다면 이 메일은 무시해도 돼요. 비밀번호는 바뀌지 않아요.\n"
        ),
    )


def invite_mail(to: str, inviter: str, group_name: str, has_account: bool) -> Mail:
    inviter, group_name = _one_line(inviter), _one_line(group_name)
    how = "로그인하면" if has_account else "가입하면"
    return Mail(
        to=to,
        subject=f"[{APP_NAME}] {inviter}님이 '{group_name}' 모임에 초대했어요",
        body=(
            f"안녕하세요, {APP_NAME}입니다.\n\n"
            f"{inviter}님이 '{group_name}' 모임에 초대했어요.\n"
            f"{APP_NAME} 앱에서 이 이메일({to})로 {how} 홈의 '받은 초대'에서 수락할 수 있어요.\n\n"
            "모르는 초대라면 이 메일은 무시해도 돼요.\n"
        ),
    )
