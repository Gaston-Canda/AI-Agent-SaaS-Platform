"""
Security utilities for JWT authentication and password hashing.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

from app.core.config import settings

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class TokenData(BaseModel):
    """Token payload structure."""
    user_id: str
    tenant_id: str
    email: str
    exp: Optional[datetime] = None


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    if not isinstance(password, str):
        password = str(password)

    password = password.strip()

    if len(password.encode("utf-8")) > 72:
        password = password.encode("utf-8")[:72].decode("utf-8")

    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(
    user_id: str,
    tenant_id: str,
    email: str,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Create a JWT access token."""
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
    
    to_encode = {
        "user_id": user_id,
        "tenant_id": tenant_id,
        "email": email,
        "exp": expire,
        "type": "access",
    }
    
    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )
    return encoded_jwt


def create_refresh_token(
    user_id: str,
    tenant_id: str,
    email: str,
) -> str:
    """Create a JWT refresh token."""
    expire = datetime.now(timezone.utc) + timedelta(
        days=settings.REFRESH_TOKEN_EXPIRE_DAYS
    )
    
    to_encode = {
        "user_id": user_id,
        "tenant_id": tenant_id,
        "email": email,
        "exp": expire,
        "type": "refresh",
    }
    
    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )
    return encoded_jwt


def verify_token(token: str) -> TokenData:
    """Verify and decode a JWT token."""
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
        user_id: str = payload.get("user_id")
        tenant_id: str = payload.get("tenant_id")
        email: str = payload.get("email")
        
        if user_id is None or tenant_id is None:
            raise JWTError("Invalid token payload")
        
        token_data = TokenData(
            user_id=user_id,
            tenant_id=tenant_id,
            email=email,
        )
        return token_data
    except JWTError:
        raise JWTError("Invalid token")
