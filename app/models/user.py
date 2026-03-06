"""
User model for authentication and multi-tenancy.
"""

from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from app.db.database import Base


class Tenant(Base):
    """Tenant model for SaaS multi-tenancy."""
    __tablename__ = "tenants"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False, unique=True)
    slug = Column(String(255), nullable=False, unique=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    # Relationships
    users = relationship("User", back_populates="tenant", cascade="all, delete-orphan")
    agents = relationship("Agent", back_populates="tenant", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index("idx_tenant_slug", "slug"),
    )


class User(Base):
    """User model for authentication."""
    __tablename__ = "users"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    email = Column(String(255), nullable=False)
    username = Column(String(255), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    tenant = relationship("Tenant", back_populates="users")
    
    __table_args__ = (
        Index("idx_user_email_tenant", "email", "tenant_id"),
        Index("idx_user_tenant_id", "tenant_id"),
    )
