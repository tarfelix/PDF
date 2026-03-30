from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel

from auth import authenticate_user, create_token, get_current_user

router = APIRouter()


class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    token: str
    name: str
    email: str
    role: str


class MeResponse(BaseModel):
    name: str
    email: str
    role: str


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest):
    user = authenticate_user(body.email, body.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou senha incorretos",
        )
    token = create_token(user)
    return LoginResponse(token=token, **user)


@router.get("/me", response_model=MeResponse)
async def me(user: dict = Depends(get_current_user)):
    return MeResponse(**user)
