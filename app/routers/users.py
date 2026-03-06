"""
User management and RBAC routes.
"""

from fastapi import APIRouter, HTTPException, status, Depends, Query
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.user import User
from app.models.extended import TenantUser, UserRole
from app.schemas.user import UserResponse
from app.schemas.extended import TenantUserResponse, UserRoleEnum
from app.services.rbac_service import RBACService
from app.core.dependencies import get_current_user, get_current_admin, get_current_owner

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    """Get current user's profile."""
    return UserResponse.model_validate(current_user)


@router.get("/tenant/members", response_model=list[TenantUserResponse])
async def list_tenant_users(
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> list[TenantUserResponse]:
    """
    List all members of the tenant.
    Only available to admins.
    """
    members = RBACService.list_tenant_users(db, current_user.tenant_id)
    return [TenantUserResponse.model_validate(m) for m in members]


@router.post("/tenant/members/{user_id}/role", response_model=TenantUserResponse)
async def assign_user_role(
    user_id: str,
    role: UserRoleEnum,
    current_user: User = Depends(get_current_owner),
    db: Session = Depends(get_db),
) -> TenantUserResponse:
    """
    Assign a role to a user in the tenant.
    Only owner can change roles.
    """
    # Convert string to enum
    role_enum = UserRole[role.value.upper()]
    
    tenant_user = RBACService.assign_role(
        db,
        user_id,
        current_user.tenant_id,
        role_enum,
    )
    
    return TenantUserResponse.model_validate(tenant_user)


@router.get("/tenant/role", response_model=UserRoleEnum)
async def get_user_role(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserRoleEnum:
    """Get current user's role in the tenant."""
    role = RBACService.get_user_role(db, current_user.id, current_user.tenant_id)
    if role is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User role not found",
        )
    return UserRoleEnum(role.value)

