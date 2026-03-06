"""
Pydantic schemas for user-related endpoints.
"""

from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime


class TenantBase(BaseModel):
    """Base tenant schema."""
    name: str = Field(..., min_length=2, max_length=120)
    slug: str = Field(..., min_length=2, max_length=120, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class TenantCreate(TenantBase):
    """Schema for creating a tenant."""
    pass


class TenantResponse(TenantBase):
    """Schema for tenant response."""
    id: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class UserBase(BaseModel):
    """Base user schema."""
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=80, pattern=r"^[a-zA-Z0-9_.-]+$")


class UserCreate(UserBase):
    """Schema for user registration."""
    password: str = Field(..., min_length=8, max_length=128)
    tenant_id: Optional[str] = None


class UserLogin(BaseModel):
    """Schema for user login."""
    email: EmailStr
    password: str


class UserResponse(UserBase):
    """Schema for user response."""
    id: str
    tenant_id: str
    is_active: bool
    is_admin: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    """Schema for token response."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshTokenRequest(BaseModel):
    """Schema for refresh token request."""
    refresh_token: str = Field(..., min_length=20, max_length=4000)
