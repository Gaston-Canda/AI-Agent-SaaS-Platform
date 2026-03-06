"""
Service for RBAC and user role management.
"""

from sqlalchemy.orm import Session
from sqlalchemy import and_, func
from typing import Optional, List
from app.models.user import User
from app.models.extended import TenantUser, UserRole


class RBACService:
    """Role-based access control service."""
    
    @staticmethod
    def assign_role(
        db: Session,
        user_id: str,
        tenant_id: str,
        role: UserRole,
    ) -> TenantUser:
        """Assign role to user in a tenant."""
        tenant_user = db.query(TenantUser).filter(
            and_(
                TenantUser.user_id == user_id,
                TenantUser.tenant_id == tenant_id,
            )
        ).first()
        
        if tenant_user:
            tenant_user.role = role
        else:
            tenant_user = TenantUser(
                user_id=user_id,
                tenant_id=tenant_id,
                role=role,
            )
            db.add(tenant_user)
        
        db.commit()
        db.refresh(tenant_user)
        return tenant_user
    
    @staticmethod
    def get_user_role(
        db: Session,
        user_id: str,
        tenant_id: str,
    ) -> Optional[UserRole]:
        """Get user's role in a tenant."""
        tenant_user = db.query(TenantUser).filter(
            and_(
                TenantUser.user_id == user_id,
                TenantUser.tenant_id == tenant_id,
            )
        ).first()
        
        return tenant_user.role if tenant_user else None
    
    @staticmethod
    def is_owner(
        db: Session,
        user_id: str,
        tenant_id: str,
    ) -> bool:
        """Check if user is owner of tenant."""
        role = RBACService.get_user_role(db, user_id, tenant_id)
        return role == UserRole.OWNER
    
    @staticmethod
    def is_admin(
        db: Session,
        user_id: str,
        tenant_id: str,
    ) -> bool:
        """Check if user is admin in tenant."""
        role = RBACService.get_user_role(db, user_id, tenant_id)
        return role in (UserRole.OWNER, UserRole.ADMIN)
    
    @staticmethod
    def list_tenant_users(
        db: Session,
        tenant_id: str,
    ) -> List[TenantUser]:
        """List all users in a tenant."""
        return db.query(TenantUser).filter(
            TenantUser.tenant_id == tenant_id,
            TenantUser.is_active == True,
        ).all()
