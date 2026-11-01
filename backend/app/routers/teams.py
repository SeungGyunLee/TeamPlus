"""팀을 만들면 8자리 초대코드가 나와요. 로그인 대신 이 코드로 팀에 들어갑니다. When2meet과 같은 방식이에요.
팀원 추가와 삭제를 할 수 있고, 한 팀에 최대 12명까지 넣을 수 있어요"""

import secrets

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_member, get_team
from app.models import Member, Team
from app.schemas import MemberCreate, MemberOut, TeamCreate, TeamOut

router = APIRouter(prefix="/teams", tags=["팀"])

# 헷갈리는 글자(0/O, 1/l/I)는 뺀 초대코드 문자
CODE_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"
CODE_LENGTH = 8
MAX_MEMBERS = 12


def _new_invite_code(db: Session) -> str:
    while True:
        code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))
        if db.scalar(select(Team.id).where(Team.invite_code == code)) is None:
            return code


@router.post("", response_model=TeamOut, status_code=201, summary="팀 만들기 (초대코드 발급)")
def create_team(body: TeamCreate, db: Session = Depends(get_db)):
    team = Team(name=body.name.strip(), invite_code=_new_invite_code(db))
    db.add(team)
    db.commit()
    db.refresh(team)
    return team


@router.get("/{code}", response_model=TeamOut, summary="초대코드로 팀 조회")
def read_team(team: Team = Depends(get_team)):
    return team


@router.post("/{code}/members", response_model=MemberOut, status_code=201, summary="팀원 추가")
def add_member(body: MemberCreate, team: Team = Depends(get_team), db: Session = Depends(get_db)):
    if len(team.members) >= MAX_MEMBERS:
        raise HTTPException(400, f"팀원은 최대 {MAX_MEMBERS}명까지 추가할 수 있어요.")
    member = Member(team_id=team.id, name=body.name.strip())
    db.add(member)
    db.commit()
    db.refresh(member)
    return member


@router.delete("/{code}/members/{member_id}", status_code=204, summary="팀원 삭제")
def delete_member(member: Member = Depends(get_member), db: Session = Depends(get_db)):
    db.delete(member)
    db.commit()
    return Response(status_code=204)
