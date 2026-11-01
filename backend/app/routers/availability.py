from fastapi import APIRouter, Depends

from app.deps import get_group, member_schedules
from app.models import Group
from app.schemas import AvailabilityOut, BlockOut
from app.services.availability import weekly_blocks
from app.timetable import period_label

router = APIRouter(tags=["공통 공강"])


@router.get(
    "/groups/{group_id}/availability",
    response_model=AvailabilityOut,
    summary="공통 공강 (월~금 × 6교시, 참석 가능 인원 많은 순)",
)
def group_availability(group: Group = Depends(get_group)):
    members = member_schedules(group)
    blocks = weekly_blocks(members)
    return AvailabilityOut(
        group_id=group.id,
        total=len(members),
        full_count=sum(1 for b in blocks if b.level == "full"),
        blocks=[
            BlockOut(
                key=b.key,
                day=b.day,
                period=b.period,
                period_label=period_label(b.period),
                count=b.count,
                total=b.total,
                level=b.level,
                available_member_ids=[m.member_id for m in b.available],
                unavailable_member_ids=[m.member_id for m in b.unavailable],
            )
            for b in blocks
        ],
    )
