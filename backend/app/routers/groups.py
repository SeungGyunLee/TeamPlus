"""모임·팀원·시간표 (프론트 홈·모임 관리·시간표 화면)."""

import secrets

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_group, get_member
from app.models import Group, Member, Reservation
from app.schemas import GroupCreate, GroupOut, GroupUpdate, MemberCreate, MemberOut, MemberUpdate
from app.timetable import DEFAULT_MEMBER_NAMES

router = APIRouter(prefix="/groups", tags=["모임"])

# 헷갈리는 글자(0/O, 1/l/I)는 뺀 초대코드 문자
CODE_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"
CODE_LENGTH = 8
MAX_MEMBERS = 12


def _new_invite_code(db: Session) -> str:
    while True:
        code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))
        if db.scalar(select(Group.id).where(Group.invite_code == code)) is None:
            return code


@router.post("", response_model=GroupOut, status_code=201, summary="모임 만들기")
def create_group(body: GroupCreate, db: Session = Depends(get_db)):
    names = DEFAULT_MEMBER_NAMES if body.member_names is None else body.member_names
    if not names:
        raise HTTPException(400, "모임에는 팀원이 한 명 이상 있어야 해요.")
    if len(names) > MAX_MEMBERS:
        raise HTTPException(400, f"팀원은 최대 {MAX_MEMBERS}명까지 추가할 수 있어요.")
    group = Group(
        name=body.name.strip(),
        owner_id=body.owner_id,
        invite_code=_new_invite_code(db),
        members=[Member(position=i, name=n.strip(), busy=[]) for i, n in enumerate(names)],
    )
    db.add(group)
    db.commit()
    db.refresh(group)
    return group


@router.get("", response_model=list[GroupOut], summary="모임 목록 (최근 수정 순)")
def list_groups(db: Session = Depends(get_db)):
    return db.scalars(select(Group).order_by(Group.updated_at.desc())).all()


@router.get("/by-invite/{code}", response_model=GroupOut, summary="초대코드로 모임 찾기")
def group_by_invite(code: str, db: Session = Depends(get_db)):
    group = db.scalar(select(Group).where(Group.invite_code == code))
    if group is None:
        raise HTTPException(404, "모임을 찾을 수 없어요. 초대코드를 확인하세요.")
    return group


@router.get("/{group_id}", response_model=GroupOut, summary="모임 조회")
def read_group(group: Group = Depends(get_group)):
    return group


@router.patch("/{group_id}", response_model=GroupOut, summary="모임 이름 바꾸기")
def rename_group(
    body: GroupUpdate, group: Group = Depends(get_group), db: Session = Depends(get_db)
):
    group.name = body.name.strip()
    group.touch()
    db.commit()
    db.refresh(group)
    return group


@router.delete("/{group_id}", status_code=204, summary="모임 삭제 (그 모임의 예약은 취소 처리)")
def delete_group(group: Group = Depends(get_group), db: Session = Depends(get_db)):
    # 프론트와 같이 예약 내역은 지우지 않고 '취소됨'으로 남긴다.
    db.execute(
        update(Reservation)
        .where(Reservation.group_id == group.id, Reservation.status == "active")
        .values(status="cancelled")
    )
    db.delete(group)
    db.commit()
    return Response(status_code=204)


@router.post("/{group_id}/members", response_model=MemberOut, status_code=201, summary="팀원 추가")
def add_member(
    body: MemberCreate, group: Group = Depends(get_group), db: Session = Depends(get_db)
):
    if len(group.members) >= MAX_MEMBERS:
        raise HTTPException(400, f"팀원은 최대 {MAX_MEMBERS}명까지 추가할 수 있어요.")
    position = max((m.position for m in group.members), default=-1) + 1
    member = Member(group_id=group.id, position=position, name=body.name.strip(), busy=body.busy)
    db.add(member)
    group.touch()
    db.commit()
    db.refresh(member)
    return member


@router.patch(
    "/{group_id}/members/{member_id}",
    response_model=MemberOut,
    summary="팀원 이름·시간표 수정 (busy는 전체 목록으로 교체)",
)
def update_member(
    body: MemberUpdate,
    member: Member = Depends(get_member),
    group: Group = Depends(get_group),
    db: Session = Depends(get_db),
):
    if body.name is not None:
        member.name = body.name.strip()
    if body.busy is not None:
        member.busy = body.busy
    group.touch()
    db.commit()
    db.refresh(member)
    return member


@router.delete("/{group_id}/members/{member_id}", status_code=204, summary="팀원 삭제")
def delete_member(
    member: Member = Depends(get_member),
    group: Group = Depends(get_group),
    db: Session = Depends(get_db),
):
    if len(group.members) <= 1:
        raise HTTPException(400, "모임에는 팀원이 한 명 이상 있어야 해요.")
    db.delete(member)
    group.touch()
    db.commit()
    return Response(status_code=204)
