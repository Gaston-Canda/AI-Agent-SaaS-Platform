"""
User service for business logic.
"""

from sqlalchemy.orm import Session
from sqlalchemy import and_
from typing import Optional
import logging

from app.models.user import User, Tenant
from app.models.extended import TenantUser, UserRole
from app.schemas.user import UserCreate, TenantCreate
from app.core.security import hash_password, verify_password

logger = logging.getLogger(__name__)


class UserService:
    """Service for user operations."""
    
    @staticmethod
    def create_tenant(db: Session, tenant_data: TenantCreate) -> Tenant:
        """Create a new tenant."""
        tenant = Tenant(name=tenant_data.name, slug=tenant_data.slug)
        db.add(tenant)
        db.commit()
        db.refresh(tenant)
        return tenant
    
    @staticmethod
    def get_tenant_by_slug(db: Session, slug: str) -> Optional[Tenant]:
        """Get tenant by slug."""
        return db.query(Tenant).filter(Tenant.slug == slug).first()
    
    @staticmethod
    def get_tenant_by_id(db: Session, tenant_id: str) -> Optional[Tenant]:
        """Get tenant by ID."""
        return db.query(Tenant).filter(Tenant.id == tenant_id).first()
    
    @staticmethod
    def create_user(db: Session, user_data: UserCreate, tenant_id: str) -> User:
        """Create a new user."""
        hashed_password = hash_password(user_data.password)
        user = User(
            email=user_data.email,
            username=user_data.username,
            hashed_password=hashed_password,
            tenant_id=tenant_id,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def register_user_with_tenant_bootstrap(
        db: Session,
        tenant_slug: str,
        user_data: UserCreate,
    ) -> tuple[User, Tenant]:
        """
        Register user in tenant with safe bootstrap.

        Behavior:
        - If tenant exists: reuse tenant
        - If tenant does not exist: create tenant and mark first user as OWNER
        """
        normalized_slug = tenant_slug.strip().lower()
        if not normalized_slug:
            raise ValueError("Tenant slug is required")

        created_tenant = False

        try:
            tenant = UserService.get_tenant_by_slug(db, normalized_slug)
            if tenant is None:
                logger.info("Bootstrapping new tenant: %s", normalized_slug)
                tenant = Tenant(
                    slug=normalized_slug,
                    name=normalized_slug,
                )
                db.add(tenant)
                db.flush()
                created_tenant = True

            existing_user = UserService.get_user_by_email(db, user_data.email, tenant.id)
            if existing_user:
                raise ValueError("Email already registered")

            user = User(
                email=user_data.email,
                username=user_data.username,
                hashed_password=hash_password(user_data.password),
                tenant_id=tenant.id,
            )
            db.add(user)
            db.flush()

            tenant_user = TenantUser(
                user_id=user.id,
                tenant_id=tenant.id,
                role=UserRole.OWNER if created_tenant else UserRole.MEMBER,
                is_active=True,
            )
            db.add(tenant_user)

            db.commit()
            db.refresh(user)
            db.refresh(tenant)
            return user, tenant
        except Exception:
            db.rollback()
            raise
    
    @staticmethod
    def get_user_by_email(db: Session, email: str, tenant_id: str) -> Optional[User]:
        """Get user by email and tenant."""
        return db.query(User).filter(
            and_(User.email == email, User.tenant_id == tenant_id)
        ).first()
    
    @staticmethod
    def get_user_by_id(db: Session, user_id: str) -> Optional[User]:
        """Get user by ID."""
        return db.query(User).filter(User.id == user_id).first()
    
    @staticmethod
    def authenticate_user(db: Session, email: str, password: str, tenant_id: str) -> Optional[User]:
        """Authenticate user with email and password."""
        user = UserService.get_user_by_email(db, email, tenant_id)
        if not user:
            return None
        if not verify_password(password, user.hashed_password):
            return None
        return user
    
    @staticmethod
    def is_user_active(user: User) -> bool:
        """Check if user is active."""
        return user.is_active and user.tenant.is_active
