"""Authentication routes: signup and login."""

from pydantic import BaseModel, EmailStr
from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth import (
    hash_password,
    verify_password,
    create_jwt_token,
)
from database import get_db_session
from models import User, PlanEnum


router = APIRouter(prefix="/auth", tags=["auth"])


class SignupRequest(BaseModel):
    username: str
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class AuthResponse(BaseModel):
    token: str
    user_id: str
    username: str
    plan: str


@router.post("/signup", response_model=AuthResponse)
async def signup(
    request: SignupRequest,
    session: AsyncSession = Depends(get_db_session),
) -> AuthResponse:
    """
    Sign up a new user.
    - Hashes password with bcrypt
    - Creates user with plan = "free"
    - Returns JWT token (expires 7 days)
    """
    # Check if user already exists
    result = await session.execute(
        select(User).where((User.email == request.email) | (User.username == request.username))
    )
    existing_user = result.scalars().first()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email or username already exists",
        )

    # Create new user
    hashed_password = hash_password(request.password)
    new_user = User(
        username=request.username,
        email=request.email,
        hashed_password=hashed_password,
        plan=PlanEnum.free,
    )

    session.add(new_user)
    await session.commit()
    await session.refresh(new_user)

    # Generate JWT token
    token = create_jwt_token(new_user.id)

    return AuthResponse(
        token=token,
        user_id=new_user.id,
        username=new_user.username,
        plan=new_user.plan.value,
    )


@router.post("/login", response_model=AuthResponse)
async def login(
    request: LoginRequest,
    session: AsyncSession = Depends(get_db_session),
) -> AuthResponse:
    """
    Log in an existing user.
    - Verifies email and password
    - Returns JWT token
    """
    result = await session.execute(select(User).where(User.email == request.email))
    user = result.scalars().first()

    if user is None or not verify_password(request.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    # Generate JWT token
    token = create_jwt_token(user.id)

    return AuthResponse(
        token=token,
        user_id=user.id,
        username=user.username,
        plan=user.plan.value,
    )
