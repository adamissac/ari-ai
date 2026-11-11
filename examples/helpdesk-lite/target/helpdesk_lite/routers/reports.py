from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["reports"])


class SlaTargets(BaseModel):
    first_reply_hours: int
    resolution_days: int
    escalation_contact: str


@router.get("/reports/sla", response_model=SlaTargets)
def sla_targets() -> SlaTargets:
    """The desk's service-level targets, shown on the agents' wallboard."""
    return SlaTargets(
        first_reply_hours=4, resolution_days=3, escalation_contact="duty-manager@example.test"
    )
