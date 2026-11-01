from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.ai import service as ai
from app.ai.client import LLMClient, LLMError
from app.db import get_db
from app.deps import get_group, require_llm
from app.models import Assignment, Group, MeetingStage
from app.schemas import AssignmentCreate, AssignmentOut, DeadlineUpdate, StageOut
from app.services.stage_planner import (
    MilestoneSpec,
    PlanningError,
    StageSpec,
    deadline_status,
    plan_stages,
)
from app.timeutil import today_kst

router = APIRouter(prefix="/groups/{group_id}/assignments", tags=["과제·회의 단계"])


def _replan(a: Assignment, today: date) -> None:
    """단계 날짜 구간을 다시 계산한다. 마감일이 없거나 지났으면 구간을 비운다."""
    specs = [StageSpec(s.name, s.purpose, s.priority) for s in a.stages]
    milestones = [
        MilestoneSpec(m["name"], date.fromisoformat(m["date"]) if m.get("date") else None)
        for m in a.milestones
    ]
    try:
        planned = plan_stages(specs, milestones, today, a.final_deadline)
    except PlanningError:
        for s in a.stages:
            s.window_start = s.window_end = s.anchored_to = None
            s.dropped = False
        return
    for s, p in zip(a.stages, planned, strict=True):
        s.window_start, s.window_end = p.window_start, p.window_end
        s.anchored_to, s.dropped = p.anchored_to, p.dropped


def _out(a: Assignment, today: date) -> AssignmentOut:
    return AssignmentOut(
        id=a.id,
        title=a.title,
        final_deadline=a.final_deadline,
        deadline_source=a.deadline_source,
        deadline_status=deadline_status(a.final_deadline, today),
        deliverable_type=a.deliverable_type,
        milestones=a.milestones,
        stages=[StageOut.model_validate(s) for s in a.stages],
    )


def _get_assignment(assignment_id: int, group: Group, db: Session) -> Assignment:
    a = db.get(Assignment, assignment_id)
    if a is None or a.group_id != group.id:
        raise HTTPException(404, "과제를 찾을 수 없어요.")
    return a


@router.post(
    "",
    response_model=AssignmentOut,
    status_code=201,
    summary="과제 공지 등록 → 회의 단계 생성 (프롬프트 2)",
)
def create_assignment(
    body: AssignmentCreate,
    group: Group = Depends(get_group),
    db: Session = Depends(get_db),
    llm: LLMClient = Depends(require_llm),
):
    today = today_kst()
    try:
        analysis = ai.analyze_assignment(llm, body.notice_text, today)
    except LLMError as e:
        raise HTTPException(502, f"공지를 분석하지 못했어요: {e}") from e

    if body.final_deadline:
        deadline, source = body.final_deadline, "user"
    elif analysis.final_deadline:
        deadline, source = analysis.final_deadline, "ai"
    else:
        deadline, source = None, None

    a = Assignment(
        group_id=group.id,
        title=body.title,
        notice_text=body.notice_text,
        final_deadline=deadline,
        deadline_source=source,
        deliverable_type=analysis.deliverable_type,
        milestones=[m.model_dump(mode="json") for m in analysis.milestones],
        stages=[
            MeetingStage(position=i, name=s.name, purpose=s.purpose, priority=s.priority)
            for i, s in enumerate(analysis.meeting_stages)
        ],
    )
    _replan(a, today)
    db.add(a)
    db.commit()
    db.refresh(a)
    return _out(a, today)


@router.get("", response_model=list[AssignmentOut], summary="모임 과제 목록")
def list_assignments(group: Group = Depends(get_group)):
    today = today_kst()
    return [_out(a, today) for a in group.assignments]


@router.get("/{assignment_id}", response_model=AssignmentOut, summary="과제와 회의 단계 조회")
def read_assignment(
    assignment_id: int, group: Group = Depends(get_group), db: Session = Depends(get_db)
):
    return _out(_get_assignment(assignment_id, group, db), today_kst())


@router.put(
    "/{assignment_id}/deadline",
    response_model=AssignmentOut,
    summary="마감일 확인·수정 → 단계 날짜 다시 계산",
)
def update_deadline(
    assignment_id: int,
    body: DeadlineUpdate,
    group: Group = Depends(get_group),
    db: Session = Depends(get_db),
):
    today = today_kst()
    a = _get_assignment(assignment_id, group, db)
    a.final_deadline, a.deadline_source = body.final_deadline, "user"
    _replan(a, today)
    db.commit()
    db.refresh(a)
    return _out(a, today)
