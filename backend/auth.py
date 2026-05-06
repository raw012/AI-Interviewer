"""Authentication utilities: JWT token handling and password hashing."""

import os
import json
from datetime import datetime, timedelta
from typing import Optional

import jwt
import httpx
from passlib.context import CryptContext
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

# Cryptography for JWK to PEM conversion (Apple OAuth2)
try:
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives import serialization
    CRYPTOGRAPHY_AVAILABLE = True
except ImportError:
    CRYPTOGRAPHY_AVAILABLE = False

from models import User
from database import get_db_session

# Try to import google.auth for Google OAuth2
try:
    from google.auth.transport import requests
    from google.oauth2 import id_token as google_id_token
    GOOGLE_AUTH_AVAILABLE = True
except ImportError:
    GOOGLE_AUTH_AVAILABLE = False


# JWT configuration
JWT_SECRET = os.getenv("JWT_SECRET", "your-secret-key-change-this-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_DAYS = 7

# OAuth2 configuration - read from environment
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_OAUTH_CLIENT_ID", "")
APPLE_CLIENT_ID = os.getenv("APPLE_OAUTH_CLIENT_ID", "")
APPLE_TEAM_ID = os.getenv("APPLE_TEAM_ID", "")
APPLE_KEY_ID = os.getenv("APPLE_KEY_ID", "")
FACEBOOK_APP_ID = os.getenv("FACEBOOK_OAUTH_APP_ID", "")
FACEBOOK_APP_SECRET = os.getenv("FACEBOOK_OAUTH_APP_SECRET", "")

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()


def hash_password(password: str) -> str:
    """Hash a plaintext password using bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a hashed password."""
    return pwd_context.verify(plain_password, hashed_password)


def create_jwt_token(user_id: str) -> str:
    """Create a JWT token for a user."""
    payload = {
        "user_id": user_id,
        "exp": datetime.utcnow() + timedelta(days=JWT_EXPIRY_DAYS),
        "iat": datetime.utcnow(),
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return token


def decode_jwt_token(token: str) -> Optional[str]:
    """Decode a JWT token and return the user_id, or None if invalid."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id: str = payload.get("user_id")
        if user_id is None:
            return None
        return user_id
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    session: AsyncSession = Depends(get_db_session),
) -> User:
    """
    JWT middleware dependency. Validates token and returns current user.
    Attach to protected routes with: Depends(get_current_user)
    """
    token = credentials.credentials
    user_id = decode_jwt_token(token)

    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Fetch user from database
    from sqlalchemy import select
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


# ============================================================================
# OAuth2 Token Verification Functions
# ============================================================================


async def verify_google_token(id_token: str) -> dict:
    """
    Verify Google ID token and extract user information.
    
    Args:
        id_token: Google ID token from frontend
        
    Returns:
        dict: Contains 'email' and 'name' keys
        
    Raises:
        HTTPException: If token is invalid
    """
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Google OAuth2 not configured (missing GOOGLE_OAUTH_CLIENT_ID)",
        )

    try:
        if not GOOGLE_AUTH_AVAILABLE:
            raise ImportError("google-auth library not installed")
            
        # Verify token signature and get claims
        request = requests.Request()
        idinfo = google_id_token.verify_oauth2_token(id_token, request, GOOGLE_CLIENT_ID)
        
        # Token is valid - extract user info
        email = idinfo.get("email")
        name = idinfo.get("name", "")
        
        if not email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Google token does not contain email claim",
            )
        
        return {"email": email, "name": name}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid Google token: {str(e)}",
        )


async def verify_apple_token(id_token: str) -> dict:
    """
    Verify Apple ID token and extract user information.
    
    Args:
        id_token: Apple ID token from frontend
        
    Returns:
        dict: Contains 'email' and 'name' keys
        
    Raises:
        HTTPException: If token is invalid
    """
    if not APPLE_CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Apple OAuth2 not configured (missing APPLE_OAUTH_CLIENT_ID)",
        )

    if not CRYPTOGRAPHY_AVAILABLE:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Cryptography library not available for Apple OAuth2",
        )

    try:
        # Decode token header to get key ID (without verification first)
        unverified_header = jwt.get_unverified_header(id_token)
        key_id = unverified_header.get("kid")
        
        if not key_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Apple token missing 'kid' header",
            )
        
        # Fetch Apple's public keys
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://appleid.apple.com/auth/keys",
                timeout=10.0,
            )
            response.raise_for_status()
            keys_data = response.json()
            keys = keys_data.get("keys", [])
        
        # Find the matching public key by kid
        signing_key_jwk = None
        for key in keys:
            if key.get("kid") == key_id:
                signing_key_jwk = key
                break
        
        if not signing_key_jwk:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Unable to find Apple signing key with kid: {key_id}",
            )
        
        # Convert JWK to PEM format for PyJWT
        # Extract JWK components (for RSA key)
        e = int.from_bytes(
            __b64_decode(signing_key_jwk.get("e", "")), 
            byteorder="big"
        )
        n = int.from_bytes(
            __b64_decode(signing_key_jwk.get("n", "")), 
            byteorder="big"
        )
        
        # Reconstruct RSA public key
        public_key = rsa.RSAPublicNumbers(e=e, n=n).public_key(default_backend())
        pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        
        # Verify token with the PEM-encoded key
        payload = jwt.decode(
            id_token,
            pem,
            algorithms=["RS256"],
            audience=APPLE_CLIENT_ID,
        )
        
        email = payload.get("email")
        if not email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Apple token does not contain email claim",
            )
        
        return {"email": email, "name": ""}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid Apple token: {str(e)}",
        )


def __b64_decode(data: str) -> bytes:
    """
    Decode base64url-encoded string (used in JWK).
    
    Base64url uses '-' and '_' instead of '+' and '/',
    and padding is optional.
    """
    # Add padding if needed
    padding = 4 - (len(data) % 4)
    if padding != 4:
        data += "=" * padding
    
    # Replace URL-safe characters with standard base64 characters
    data = data.replace("-", "+").replace("_", "/")
    
    try:
        return __import__("base64").b64decode(data)
    except Exception as e:
        raise ValueError(f"Failed to decode base64url: {e}")




async def verify_facebook_token(access_token: str) -> dict:
    """
    Verify Facebook access token and extract user information.
    
    Args:
        access_token: Facebook access token from frontend
        
    Returns:
        dict: Contains 'email' and 'name' keys
        
    Raises:
        HTTPException: If token is invalid
    """
    if not FACEBOOK_APP_ID or not FACEBOOK_APP_SECRET:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Facebook OAuth2 not configured (missing credentials)",
        )

    try:
        async with httpx.AsyncClient() as client:
            # Validate token and get user info
            response = await client.get(
                "https://graph.facebook.com/me",
                params={
                    "access_token": access_token,
                    "fields": "id,email,name",
                },
            )
            response.raise_for_status()
            user_data = response.json()
        
        # Check for errors
        if "error" in user_data:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Facebook token validation failed: {user_data['error'].get('message', 'Unknown error')}",
            )
        
        email = user_data.get("email")
        name = user_data.get("name", "")
        
        if not email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Facebook token does not contain email",
            )
        
        return {"email": email, "name": name}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid Facebook token: {str(e)}",
        )

