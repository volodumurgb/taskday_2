from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import update

from app.auth import get_current_user
from app.db import Session
from app.models import User, Wallet

router = APIRouter(prefix="/wallet", tags=["wallet"])

class TopUpRequest(BaseModel):
    amount: Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=2)]


class BalanceResponse(BaseModel):
    balance: Decimal


@router.post("/top-up")
async def top_up(
    payload: TopUpRequest,
    user: Annotated[User, Depends(get_current_user)],
) -> BalanceResponse:
    """Add funds to the authenticated user's wallet and return its balance."""
    async with Session.begin() as session:
        statement = (
            update(Wallet)
            .where(Wallet.user_id == user.id)
            .values(balance=Wallet.balance + payload.amount)
            .returning(Wallet.balance)
        )
        balance = await session.scalar(statement)

        if balance is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Wallet not found",
            )

    return BalanceResponse(balance=balance)
