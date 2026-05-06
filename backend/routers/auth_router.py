"""Authentication routes: signup and login."""

from pydantic import BaseModel, EmailStr
from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth import (
    hash_password,
    verify_password,
    create_jwt_token,
    verify_google_token,
    verify_apple_token,
    verify_facebook_token,
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


class GoogleOAuthRequest(BaseModel):
    id_token: str


class AppleOAuthRequest(BaseModel):
    id_token: str


class FacebookOAuthRequest(BaseModel):
    access_token: str


class AuthResponse(BaseModel):
    token: str
    user_id: str
    username: str
    plan: str


# ============================================================================
# Helper Functions
# ============================================================================


async def get_or_create_oauth_user(
    email: str,
    name: str,
    session: AsyncSession,
) -> User:
    """
    Get or create a user based on email from OAuth provider.
    
    - If user exists by email, return existing user
    - If user does not exist, create new user with plan = "free"
    - Generate username from email if name is not provided
    
    Args:
        email: User's email from OAuth provider
        name: User's name from OAuth provider (may be empty string)
        session: Database session
        
    Returns:
        User object (existing or newly created)
    """
    # Try to find existing user by email
    result = await session.execute(
        select(User).where(User.email == email)
    )
    existing_user = result.scalars().first()

    if existing_user:
        return existing_user

    # Create new user
    # Generate username from email (remove domain part)
    base_username = email.split("@")[0]
    username = base_username
    
    # If name is provided and not empty, use it as username
    if name and name.strip():
        # Sanitize name: remove spaces, keep only alphanumeric and underscore
        sanitized_name = "".join(c for c in name.replace(" ", "_") if c.isalnum() or c == "_")
        username = sanitized_name if sanitized_name else base_username

    # Handle username collision by appending a number
    username_counter = 1
    while True:
        result = await session.execute(
            select(User).where(User.username == username)
        )
        if result.scalars().first() is None:
            break
        username = f"{base_username}_{username_counter}"
        username_counter += 1

    # Create new user with no password (OAuth user)
    # Use a placeholder hashed password
    new_user = User(
        username=username,
        email=email,
        hashed_password="",  # OAuth users don't have passwords
        plan=PlanEnum.free,
    )

    session.add(new_user)
    await session.commit()
    await session.refresh(new_user)

    return new_user


# ============================================================================
# Original Routes (Unchanged)
# ============================================================================


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


# ============================================================================
# OAuth2 Routes
# ============================================================================


@router.post("/google", response_model=AuthResponse)
async def google_oauth(
    request: GoogleOAuthRequest,
    session: AsyncSession = Depends(get_db_session),
) -> AuthResponse:
    """
    Google OAuth2 login endpoint.
    
    Request body:
    {
        "id_token": "<Google ID token from frontend>"
    }
    
    Flow:
    1. Verify Google ID token signature
    2. Extract email and name from token
    3. Get or create user in database
    4. Return JWT token
    
    Returns:
        AuthResponse: token, user_id, username, plan
    """
    # Verify Google token and extract user info
    user_info = await verify_google_token(request.id_token)
    
    # Get or create user in database
    user = await get_or_create_oauth_user(
        email=user_info["email"],
        name=user_info["name"],
        session=session,
    )
    
    # Generate JWT token
    token = create_jwt_token(user.id)

    return AuthResponse(
        token=token,
        user_id=user.id,
        username=user.username,
        plan=user.plan.value,
    )


@router.post("/apple", response_model=AuthResponse)
async def apple_oauth(
    request: AppleOAuthRequest,
    session: AsyncSession = Depends(get_db_session),
) -> AuthResponse:
    """
    Apple Sign In OAuth2 login endpoint.
    
    Request body:
    {
        "id_token": "<Apple ID token from frontend>"
    }
    
    Flow:
    1. Verify Apple ID token signature using Apple's public keys
    2. Extract email from token claims
    3. Get or create user in database
    4. Return JWT token
    
    Returns:
        AuthResponse: token, user_id, username, plan
    """
    # Verify Apple token and extract user info
    user_info = await verify_apple_token(request.id_token)
    
    # Get or create user in database
    user = await get_or_create_oauth_user(
        email=user_info["email"],
        name=user_info["name"],
        session=session,
    )
    
    # Generate JWT token
    token = create_jwt_token(user.id)

    return AuthResponse(
        token=token,
        user_id=user.id,
        username=user.username,
        plan=user.plan.value,
    )


@router.post("/facebook", response_model=AuthResponse)
async def facebook_oauth(
    request: FacebookOAuthRequest,
    session: AsyncSession = Depends(get_db_session),
) -> AuthResponse:
    """
    Facebook OAuth2 login endpoint.
    
    Request body:
    {
        "access_token": "<Facebook access token from frontend>"
    }
    
    Flow:
    1. Validate Facebook access token via Graph API
    2. Extract email and name from user data
    3. Get or create user in database
    4. Return JWT token
    
    Returns:
        AuthResponse: token, user_id, username, plan
        
    Note:
        Facebook may not always return email; ensure user enables email permissions
        in the login flow on the frontend.
    """
    # Verify Facebook token and extract user info
    user_info = await verify_facebook_token(request.access_token)
    
    # Get or create user in database
    user = await get_or_create_oauth_user(
        email=user_info["email"],
        name=user_info["name"],
        session=session,
    )
    
    # Generate JWT token
    token = create_jwt_token(user.id)

    return AuthResponse(
        token=token,
        user_id=user.id,
        username=user.username,
        plan=user.plan.value,
    )

