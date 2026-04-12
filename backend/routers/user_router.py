"""User routes: plan and quota information."""

from datetime import datetime
from pydantic import BaseModel
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from auth import get_current_user
from database import get_db_session
from models import User
from services.ai_gateway import get_redis_client


router = APIRouter(prefix="/user", tags=["user"])


class QuotaResponse(BaseModel):
    plan: str
    requests_used_today: int
    limit: int


@router.get("/quota", response_model=QuotaResponse)
async def get_quota(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> QuotaResponse:
    """
    Get user's quota information.
    - For free users: returns used/limit for today
    - For pro users: returns limit as -1 (unlimited)
    """
    plan = current_user.plan.value

    if plan == "pro":
        return QuotaResponse(
            plan=plan,
            requests_used_today=0,
            limit=-1,  # -1 indicates unlimited
        )

    # Free user: check Redis for today's count
    redis_client = await get_redis_client()
    today = datetime.utcnow().strftime("%Y-%m-%d")
    rate_limit_key = f"rate_limit:{current_user.id}:{today}"
    
    current_count = await redis_client.get(rate_limit_key)
    current_count = int(current_count) if current_count else 0

    return QuotaResponse(
        plan=plan,
        requests_used_today=current_count,
        limit=10,
    )
