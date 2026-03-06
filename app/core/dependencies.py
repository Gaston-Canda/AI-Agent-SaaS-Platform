"""
Dependency injection for FastAPI with RBAC support.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from jose import JWTError

from app.db.database import get_db
from app.core.security import verify_token
from app.models.user import User
from app.models.extended import UserRole
from app.services.user_service import UserService
from app.services.rbac_service import RBACService
from app.services.usage_service import UsageService
from app.monitoring.audit_logger import AuditLogger

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    """Get current authenticated user."""
    token = credentials.credentials
    
    try:
        token_data = verify_token(token)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user = UserService.get_user_by_id(db, token_data.user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    
    if not UserService.is_user_active(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not active",
        )
    
    return user


async def get_current_admin(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    """Get current authenticated admin user in tenant."""
    if not RBACService.is_admin(db, current_user.id, current_user.tenant_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user


async def get_current_owner(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    """Get current user if they are owner of tenant."""
    if not RBACService.is_owner(db, current_user.id, current_user.tenant_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Owner access required",
        )
    return current_user


async def check_execution_quota(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> bool:
    """Check if tenant has execution quota available."""
    quota_status = UsageService.check_quota(db, current_user.tenant_id)
    
    if quota_status.get("daily_exceeded"):
        AuditLogger.log_event(
            db=db,
            action="quota_exceeded_daily",
            tenant_id=current_user.tenant_id,
            user_id=current_user.id,
            metadata=quota_status,
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Daily execution quota exceeded. Please upgrade your plan.",
        )

    if quota_status.get("monthly_tokens_exceeded"):
        AuditLogger.log_event(
            db=db,
            action="quota_exceeded_tokens",
            tenant_id=current_user.tenant_id,
            user_id=current_user.id,
            metadata=quota_status,
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Monthly token quota exceeded. Please upgrade your plan.",
        )

    if quota_status.get("monthly_executions_exceeded"):
        AuditLogger.log_event(
            db=db,
            action="quota_exceeded_executions_month",
            tenant_id=current_user.tenant_id,
            user_id=current_user.id,
            metadata=quota_status,
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Monthly execution quota exceeded. Please upgrade your plan.",
        )

    if quota_status.get("monthly_tool_calls_exceeded"):
        AuditLogger.log_event(
            db=db,
            action="quota_exceeded_tool_calls_month",
            tenant_id=current_user.tenant_id,
            user_id=current_user.id,
            metadata=quota_status,
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Monthly tool-call quota exceeded. Please upgrade your plan.",
        )
    
    return True


async def check_agent_creation_quota(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> bool:
    """Check if tenant can create more agents according to subscription plan."""
    quota_status = UsageService.check_agent_quota(db, current_user.tenant_id)
    if quota_status.get("agents_exceeded"):
        AuditLogger.log_event(
            db=db,
            action="quota_exceeded_agents",
            tenant_id=current_user.tenant_id,
            user_id=current_user.id,
            metadata=quota_status,
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Agent quota exceeded for current plan. Please upgrade your plan.",
        )
    return True
