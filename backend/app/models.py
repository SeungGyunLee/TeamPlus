"""DB 테이블 정의 (SQLAlchemy 2.0). 필드는 프론트 src/domain/model.ts에 맞춘다."""

import secrets
from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.timeutil import now_kst


def new_id() -> str:
    """프론트 uid()처럼 짧은 문자열 ID"""
    return secrets.token_hex(8)


class User(Base):
    """계정 (와이어프레임 3A·3B). 학번·실명은 받지 않는다."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    # 소문자로 저장해서 대소문자가 달라도 같은 계정으로 본다
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    nickname: Mapped[str] = mapped_column(String(30))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_kst)


class AuthToken(Base):
    """로그인 토큰. 원문은 사용자에게만 주고 DB에는 SHA-256 해시만 저장한다."""

    __tablename__ = "auth_tokens"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_kst)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class PasswordReset(Base):
    """비밀번호 재설정 인증 코드 (메일로 보낸 6자리). 코드 원문은 저장하지 않는다."""

    __tablename__ = "password_resets"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    code_hash: Mapped[str] = mapped_column(String(64))
    attempts: Mapped[int] = mapped_column(Integer, default=0)  # 틀린 횟수
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_kst)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Group(Base):
    """모임 (프론트 Group)"""

    __tablename__ = "groups"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(100))
    # 모임을 만든 사용자 id (삭제 권한)
    owner_id: Mapped[str] = mapped_column(String(64), default="local-owner")
    # 초대 기능용 (프론트는 아직 null). 미리 발급해 둔다.
    invite_code: Mapped[str | None] = mapped_column(String(16), unique=True, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_kst)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_kst)

    members: Mapped[list["Member"]] = relationship(
        back_populates="group", cascade="all, delete-orphan", order_by="Member.position"
    )
    assignments: Mapped[list["Assignment"]] = relationship(
        back_populates="group", cascade="all, delete-orphan", order_by="Assignment.id"
    )

    def touch(self) -> None:
        self.updated_at = now_kst()


class Member(Base):
    """팀원 (프론트 Member). busy = 수업 있는 블록 키 목록 ["0-0", "1-2", ...]

    세 종류가 있다.
    - 계정이 연결된 팀원: user_id 있음, status=joined (와이어프레임 '참여완료', 본인은 '나')
    - 이메일로 초대만 된 팀원: user_id 없음, email 있음, status=invited ('대기중')
    - 이름만 있는 팀원: user_id·email 없음, status=joined (계정 없이 시간표만 대신 입력)
    """

    __tablename__ = "members"
    __table_args__ = (
        Index("uq_member_group_user", "group_id", "user_id", unique=True),
        Index("uq_member_group_email", "group_id", "email", unique=True),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    group_id: Mapped[str] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    name: Mapped[str] = mapped_column(String(50))
    user_id: Mapped[str | None] = mapped_column(String(64), default=None)
    email: Mapped[str | None] = mapped_column(String(254), default=None, index=True)
    status: Mapped[str] = mapped_column(String(10), default="joined")  # joined | invited
    # 이메일로 초대한 사용자 id (5B '○○ 님이 초대했어요')
    invited_by: Mapped[str | None] = mapped_column(String(32), default=None)
    busy: Mapped[list] = mapped_column(JSON, default=list)

    group: Mapped[Group] = relationship(back_populates="members")


class Assignment(Base):
    """과제 공지 + AI가 뽑은 마감일·중간 일정 (프롬프트 2)"""

    __tablename__ = "assignments"

    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[str] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"), index=True)
    title: Mapped[str | None] = mapped_column(String(200), default=None)
    notice_text: Mapped[str] = mapped_column(Text)
    final_deadline: Mapped[date | None] = mapped_column(Date, default=None)
    # 마감일 출처: user(직접 입력) | ai(공지에서 추출, 사용자 확인 필요)
    deadline_source: Mapped[str | None] = mapped_column(String(10), default=None)
    deliverable_type: Mapped[str] = mapped_column(String(20))
    # [{"name": "중간발표", "date": "2026-11-20" | null}, ...]
    milestones: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_kst)

    group: Mapped[Group] = relationship(back_populates="assignments")
    stages: Mapped[list["MeetingStage"]] = relationship(
        back_populates="assignment",
        cascade="all, delete-orphan",
        order_by="MeetingStage.position",
    )


class MeetingStage(Base):
    """회의 단계. 이름·목적·우선순위는 AI, 날짜 구간(window)은 코드가 정한다."""

    __tablename__ = "meeting_stages"

    id: Mapped[int] = mapped_column(primary_key=True)
    assignment_id: Mapped[int] = mapped_column(
        ForeignKey("assignments.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int] = mapped_column(Integer)
    # 이름·목적·묶인 중간 일정 이름은 AI가 만든 문장이라 길이를 정할 수 없다.
    # (PostgreSQL은 정해진 길이를 넘으면 저장에 실패한다)
    name: Mapped[str] = mapped_column(Text)
    purpose: Mapped[str] = mapped_column(Text)
    priority: Mapped[str] = mapped_column(String(10))  # must | optional
    window_start: Mapped[date | None] = mapped_column(Date, default=None)
    window_end: Mapped[date | None] = mapped_column(Date, default=None)
    anchored_to: Mapped[str | None] = mapped_column(Text, default=None)
    dropped: Mapped[bool] = mapped_column(default=False)

    assignment: Mapped[Assignment] = relationship(back_populates="stages")
