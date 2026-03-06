"""
Authentication routes.
"""

from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy.orm import Session
from datetime import timedelta

from app.db.database import get_db
from app.schemas.user import (
    UserCreate, UserResponse, UserLogin, TokenResponse, RefreshTokenRequest, TenantCreate
)
from app.services.user_service import UserService
from app.core.security import (
    create_access_token, create_refresh_token, verify_token
)
from app.core.config import settings
from jose import JWTError
from app.monitoring.audit_logger import AuditLogger

router = APIRouter(prefix="/api/auth", tags=["authentication"])


@router.post("/register", response_model=dict)
async def register(
    tenant_slug: str,
    user_data: UserCreate,
    db: Session = Depends(get_db),
) -> dict:
    """
    Register a new user in a tenant.
    
    Creates a new user account in the specified tenant.
    """
    try:
        user, _tenant = UserService.register_user_with_tenant_bootstrap(
            db=db,
            tenant_slug=tenant_slug,
            user_data=user_data,
        )
    except ValueError as exc:
        AuditLogger.log_event(
            db=db,
            action="auth_register_failed",
            tenant_id=None,
            user_id=None,
            metadata={"tenant_slug": tenant_slug, "reason": str(exc)},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    
    # Generate tokens
    access_token = create_access_token(
        user_id=user.id,
        tenant_id=user.tenant_id,
        email=user.email,
    )

    AuditLogger.log_event(
        db=db,
        action="auth_refresh_success",
        tenant_id=user.tenant_id,
        user_id=user.id,
        metadata={},
    )
    refresh_token = create_refresh_token(
        user_id=user.id,
        tenant_id=user.tenant_id,
        email=user.email,
    )

    AuditLogger.log_event(
        db=db,
        action="auth_register_success",
        tenant_id=user.tenant_id,
        user_id=user.id,
        metadata={"tenant_slug": tenant_slug},
    )
    
    return {
        "user": UserResponse.model_validate(user),
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


@router.post("/login", response_model=dict)
async def login(
    tenant_slug: str,
    credentials: UserLogin,
    db: Session = Depends(get_db),
) -> dict:
    """
    Login user and receive tokens.
    
    Authenticates user with email and password, returns access and refresh tokens.
    """
    # Get tenant
    tenant = UserService.get_tenant_by_slug(db, tenant_slug)
    if not tenant:
        AuditLogger.log_event(
            db=db,
            action="auth_login_failed",
            tenant_id=None,
            user_id=None,
            metadata={"tenant_slug": tenant_slug, "reason": "tenant_not_found"},
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )
    
    # Authenticate user
    user = UserService.authenticate_user(
        db,
        credentials.email,
        credentials.password,
        tenant.id,
    )
    
    if not user:
        AuditLogger.log_event(
            db=db,
            action="auth_login_failed",
            tenant_id=tenant.id,
            user_id=None,
            metadata={"reason": "invalid_credentials", "email": credentials.email},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not UserService.is_user_active(user):
        AuditLogger.log_event(
            db=db,
            action="auth_login_failed",
            tenant_id=user.tenant_id,
            user_id=user.id,
            metadata={"reason": "inactive_user"},
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not active",
        )
    
    # Generate tokens
    access_token = create_access_token(
        user_id=user.id,
        tenant_id=user.tenant_id,
        email=user.email,
    )
    refresh_token = create_refresh_token(
        user_id=user.id,
        tenant_id=user.tenant_id,
        email=user.email,
    )

    AuditLogger.log_event(
        db=db,
        action="auth_login_success",
        tenant_id=user.tenant_id,
        user_id=user.id,
        metadata={"tenant_slug": tenant_slug},
    )
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": UserResponse.model_validate(user),
    }


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: RefreshTokenRequest,
    db: Session = Depends(get_db),
) -> TokenResponse:
    """
    Refresh access token using refresh token.
    
    Exchange a refresh token for a new access token.
    """
    try:
        token_data = verify_token(request.refresh_token)
    except JWTError:
        AuditLogger.log_event(
            db=db,
            action="auth_refresh_failed",
            tenant_id=None,
            user_id=None,
            metadata={"reason": "invalid_refresh_token"},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )
    
    user = UserService.get_user_by_id(db, token_data.user_id)
    if not user or not UserService.is_user_active(user):
        AuditLogger.log_event(
            db=db,
            action="auth_refresh_failed",
            tenant_id=token_data.tenant_id,
            user_id=token_data.user_id,
            metadata={"reason": "user_not_found_or_inactive"},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )
    
    access_token = create_access_token(
        user_id=user.id,
        tenant_id=user.tenant_id,
        email=user.email,
    )
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=request.refresh_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
