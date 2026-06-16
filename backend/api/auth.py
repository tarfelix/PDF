from fastapi import APIRouter, Depends
from pydantic import BaseModel

from auth import get_current_user

router = APIRouter()


class MeResponse(BaseModel):
    name: str
    email: str
    role: str


@router.get("/me", response_model=MeResponse)
async def me(user: dict = Depends(get_current_user)):
    """Usuario corrente a partir dos headers do oauth2-proxy. Login local removido."""
    return MeResponse(**user)
