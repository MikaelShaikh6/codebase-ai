from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlmodel import Session, select

from app.core.auth import create_access_token, hash_password, verify_password
from app.core.database import engine
from app.core.rate_limit import rate_limit
from app.models.user import User

router = APIRouter(prefix="/auth", tags=["auth"])


class AuthRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post(
    "/register",
    response_model=AuthResponse,
    dependencies=[Depends(rate_limit("register", max_requests=5, window_seconds=3600))],
)
def register(request: AuthRequest) -> AuthResponse:
    email = request.email.lower()
    with Session(engine) as session:
        if session.exec(select(User).where(User.email == email)).first():
            raise HTTPException(status_code=409, detail="An account with that email already exists.")
        user = User(id=str(uuid4()), email=email, password_hash=hash_password(request.password))
        session.add(user)
        session.commit()
    return AuthResponse(access_token=create_access_token(user.id))


@router.post(
    "/login",
    response_model=AuthResponse,
    dependencies=[Depends(rate_limit("login", max_requests=10, window_seconds=900))],
)
def login(request: AuthRequest) -> AuthResponse:
    with Session(engine) as session:
        user = session.exec(select(User).where(User.email == request.email.lower())).first()
    if user is None or not verify_password(request.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    return AuthResponse(access_token=create_access_token(user.id))
