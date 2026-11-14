"""Public deterministic finance tools used by the agent orchestrator."""

from fastapi import APIRouter

from app.schemas.finance import FinanceEstimateRequest, FinanceEstimateResponse
from app.services.finance_service import estimate_finance

router = APIRouter(prefix="/api/v1/finance", tags=["finance"])


@router.post("/estimate", response_model=FinanceEstimateResponse)
async def estimate(request: FinanceEstimateRequest) -> FinanceEstimateResponse:
    """Estimate published charges without allowing the LLM to perform arithmetic."""
    return estimate_finance(request)
