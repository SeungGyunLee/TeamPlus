"""모임·팀원·시간표·초대 (와이어프레임 4 홈, 5 모임 초대, 6 시간표 입력).

권한
- 로그인 필요. 내가 '참여완료'인 모임만 보인다.
- 모임 삭제: 만든 사람만
- 시간표·이름 수정: 본인 것, 또는 계정 없는 팀원(이름만 있는 팀원) 것
- 팀원 내보내기: 초대 대기중·이름만 있는 팀원은 누구나, 계정 있는 팀원은 만든 사람만
- 본인은 '나가기' 가능 (만든 사람은 나갈 수 없고 모임을 삭제해야 함)
"""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user, get_group, get_mailer, get_member, joined_members
from app.models import Group, Member, User
from app.schemas import (
    GroupCreate,
    GroupOut,
    GroupUpdate,
    InviteCreate,
    InviteOut,
    MemberCreate,
    MemberOut,
    MemberUpdate,
)
from app.services.auth import is_valid_email, normalize_email
from app.services.mail import Mailer, invite_mail, send_safely

router = APIRouter(prefix="/groups", tags=["모임"])

MAX_MEMBERS = 12  # 초대 대기중 포함


def _next_position(group: Group) -> int:
    return max((m.position for m in group.members), default=-1) + 1


def _check_room(group: Group) -> None:
    if len(group.members) >= MAX_MEMBERS:
        raise HTTPException(400, f"팀원은 최대 {MAX_MEMBERS}명까지 추가할 수 있어요.")


@router.post(
    "", response_model=GroupOut, status_code=201, summary="모임 만들기 (만든 사람 자동 참여)"
)
def create_group(
    body: GroupCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    group = Group(name=body.name.strip(), owner_id=user.id, invite_code=None)
    group.members.append(
        Member(position=0, name=user.nickname, user_id=user.id, email=user.email, status="joined")
    )
    for i, n in enumerate(body.member_names, start=1):
        group.members.append(Member(position=i, name=n.strip(), status="joined"))
    db.add(group)
    db.commit()
    db.refresh(group)
    return group


@router.get("", response_model=list[GroupOut], summary="내 모임 목록 (최근 수정 순)")
def list_groups(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    mine = select(Member.group_id).where(Member.user_id == user.id, Member.status == "joined")
    return db.scalars(
        select(Group).where(Group.id.in_(mine)).order_by(Group.updated_at.desc())
    ).all()


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


@router.delete("/{group_id}", status_code=204, summary="모임 삭제 (만든 사람만)")
def delete_group(
    group: Group = Depends(get_group),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if group.owner_id != user.id:
        raise HTTPException(403, "모임을 만든 사람만 삭제할 수 있어요.")
    db.delete(group)
    db.commit()
    return Response(status_code=204)


@router.post(
    "/{group_id}/invites",
    response_model=MemberOut,
    status_code=201,
    summary="이메일로 초대 (5A, 상태: 대기중) + 초대 메일 발송",
)
def invite(
    body: InviteCreate,
    background: BackgroundTasks,
    group: Group = Depends(get_group),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    mailer: Mailer = Depends(get_mailer),
):
    email = normalize_email(body.email)
    if not is_valid_email(email):
        raise HTTPException(422, "이메일 형식을 확인해 주세요.")
    if any(m.email == email for m in group.members):
        raise HTTPException(409, "이미 초대했거나 참여 중인 이메일이에요.")
    _check_room(group)
    member = Member(
        group_id=group.id,
        position=_next_position(group),
        name=email.split("@")[0][:50],  # 수락 전 표시 이름 (팀원 이름 칸은 50자)
        email=email,
        status="invited",
        invited_by=user.id,
    )
    db.add(member)
    group.touch()
    db.commit()
    db.refresh(member)
    has_account = db.scalar(select(User.id).where(User.email == email)) is not None
    background.add_task(
        send_safely, mailer, invite_mail(email, user.nickname, group.name, has_account)
    )
    return member


@router.post(
    "/{group_id}/members",
    response_model=MemberOut,
    status_code=201,
    summary="계정 없는 팀원 추가 (이름만, 시간표는 대신 입력)",
)
def add_member(
    body: MemberCreate, group: Group = Depends(get_group), db: Session = Depends(get_db)
):
    _check_room(group)
    member = Member(
        group_id=group.id,
        position=_next_position(group),
        name=body.name.strip(),
        busy=body.busy,
        status="joined",
    )
    db.add(member)
    group.touch()
    db.commit()
    db.refresh(member)
    return member


@router.patch(
    "/{group_id}/members/{member_id}",
    response_model=MemberOut,
    summary="팀원 이름·시간표 수정 (본인 또는 계정 없는 팀원만, busy는 전체 교체)",
)
def update_member(
    body: MemberUpdate,
    member: Member = Depends(get_member),
    group: Group = Depends(get_group),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    is_me = member.user_id == user.id
    is_name_only = member.user_id is None and member.status == "joined"
    if not (is_me or is_name_only):
        raise HTTPException(403, "다른 팀원의 정보는 바꿀 수 없어요.")
    if body.name is not None:
        member.name = body.name.strip()
    if body.busy is not None:
        member.busy = body.busy
    group.touch()
    db.commit()
    db.refresh(member)
    return member


@router.delete(
    "/{group_id}/members/{member_id}",
    status_code=204,
    summary="팀원 내보내기·초대 취소·모임 나가기",
)
def delete_member(
    member: Member = Depends(get_member),
    group: Group = Depends(get_group),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    is_owner = group.owner_id == user.id
    if member.user_id == group.owner_id:
        raise HTTPException(400, "모임을 만든 사람은 나갈 수 없어요. 모임을 삭제해 주세요.")
    if member.user_id is not None and member.user_id != user.id and not is_owner:
        raise HTTPException(403, "다른 팀원은 모임을 만든 사람만 내보낼 수 있어요.")
    if member.status == "joined" and len(joined_members(group)) <= 1:
        raise HTTPException(400, "모임에는 팀원이 한 명 이상 있어야 해요.")
    db.delete(member)
    group.touch()
    db.commit()
    return Response(status_code=204)


# ---------- 나에게 온 초대 ----------
invites_router = APIRouter(prefix="/invites", tags=["모임"])


def _my_invite(member_id: str, user: User, db: Session) -> Member:
    m = db.get(Member, member_id)
    if m is None or m.status != "invited" or m.email != user.email:
        raise HTTPException(404, "초대를 찾을 수 없어요.")
    return m


@invites_router.get(
    "",
    response_model=list[InviteOut],
    summary="나에게 온 초대 목록 (내 이메일로 초대된 대기중 모임)",
)
def my_invites(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(
        select(Member).where(Member.email == user.email, Member.status == "invited")
    ).all()
    inviters = {
        u.id: u.nickname
        for u in db.scalars(select(User).where(User.id.in_({m.invited_by for m in rows})))
    }
    return [
        InviteOut(
            member_id=m.id,
            group_id=m.group_id,
            group_name=m.group.name,
            inviter_name=inviters.get(m.invited_by),
            member_count=len(joined_members(m.group)),
        )
        for m in rows
    ]


@invites_router.post("/{member_id}/accept", response_model=GroupOut, summary="초대 수락 (참여완료)")
def accept_invite(
    member_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    m = _my_invite(member_id, user, db)
    already = db.scalar(
        select(Member.id).where(Member.group_id == m.group_id, Member.user_id == user.id)
    )
    if already is not None:
        raise HTTPException(409, "이미 참여 중인 모임이에요.")
    m.user_id, m.status, m.name = user.id, "joined", user.nickname
    m.group.touch()
    db.commit()
    db.refresh(m.group)
    return m.group


@invites_router.post("/{member_id}/decline", status_code=204, summary="초대 거절")
def decline_invite(
    member_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    m = _my_invite(member_id, user, db)
    m.group.touch()
    db.delete(m)
    db.commit()
    return Response(status_code=204)
