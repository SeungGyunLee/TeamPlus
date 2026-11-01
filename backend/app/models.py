"""DB 테이블 정의 (SQLAlchemy 2.0). 필드는 프론트 src/domain/model.ts에 맞춘다."""

import secrets
from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.timeutil import now_kst


def new_id() -> str:
    """프론트 uid()처럼 짧은 문자열 ID"""
    return secrets.token_hex(8)


class Group(Base):
    """모임 (프론트 Group)"""

    __tablename__ = "groups"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(100))
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
    """팀원 (프론트 Member). busy = 수업 있는 블록 키 목록 ["0-0", "1-2", ...]"""

    __tablename__ = "members"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    group_id: Mapped[str] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    name: Mapped[str] = mapped_column(String(50))
    user_id: Mapped[str | None] = mapped_column(String(64), default=None)
    busy: Mapped[list] = mapped_column(JSON, default=list)

    group: Mapped[Group] = relationship(back_populates="members")


class Reservation(Base):
    """가상 예약 (프론트 Reservation).

    모임을 지워도 예약 내역은 '취소됨'으로 남아야 하므로 group_id에 외래키를 걸지 않고
    모임 이름을 함께 저장한다.
    """

    __tablename__ = "reservations"
    __table_args__ = (
        # 같은 방·날짜·시간에 활성 예약은 하나만 (동시 요청이 와도 DB가 막는다)
        Index(
            "uq_active_room_slot",
            "room_id",
            "date",
            "hour",
            unique=True,
            sqlite_where=text("status = 'active'"),
            postgresql_where=text("status = 'active'"),
        ),
        # 같은 모임은 같은 시간에 활성 예약 하나만
        Index(
            "uq_active_group_slot",
            "group_id",
            "date",
            "hour",
            unique=True,
            sqlite_where=text("status = 'active'"),
            postgresql_where=text("status = 'active'"),
        ),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    group_id: Mapped[str] = mapped_column(String(32), index=True)
    group_name: Mapped[str] = mapped_column(String(100))
    room_id: Mapped[str] = mapped_column(String(32))
    date: Mapped[date] = mapped_column(Date)
    hour: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(10), default="active")  # active | cancelled
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_kst)


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
    name: Mapped[str] = mapped_column(String(100))
    purpose: Mapped[str] = mapped_column(String(300))
    priority: Mapped[str] = mapped_column(String(10))  # must | optional
    window_start: Mapped[date | None] = mapped_column(Date, default=None)
    window_end: Mapped[date | None] = mapped_column(Date, default=None)
    anchored_to: Mapped[str | None] = mapped_column(String(100), default=None)
    dropped: Mapped[bool] = mapped_column(default=False)

    assignment: Mapped[Assignment] = relationship(back_populates="stages")
