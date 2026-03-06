"""Database bootstrap script for first-run and repeatable deployments."""

from __future__ import annotations

import os
import secrets
from datetime import datetime

from sqlalchemy import inspect, text

from app.core.initialization import initialize_application
from app.core.security import hash_password
from app.db.database import Base, SessionLocal, engine
from app.models.extended import TenantUser, UserRole
from app.models.user import Tenant, User


def _bool_from_env(name: str, default: bool = True) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


def run_migrations_or_create_tables() -> None:
    """Run migrations if configured; otherwise create tables directly."""
    # This project currently uses SQLAlchemy metadata bootstrap.
    Base.metadata.create_all(bind=engine)


def ensure_default_tenant_and_admin() -> tuple[Tenant, User, bool, bool, str]:
    """Create default tenant/admin if missing. Returns entity references and created flags."""
    default_tenant_slug = os.getenv("DEFAULT_TENANT_SLUG", "default")
    default_tenant_name = os.getenv("DEFAULT_TENANT_NAME", "Default Tenant")

    default_admin_email = os.getenv("DEFAULT_ADMIN_EMAIL", "admin@example.com")
    default_admin_username = os.getenv("DEFAULT_ADMIN_USERNAME", "admin")
    default_admin_password = os.getenv("DEFAULT_ADMIN_PASSWORD") or secrets.token_urlsafe(16)

    db = SessionLocal()
    created_tenant = False
    created_user = False
    try:
        tenant = db.query(Tenant).filter(Tenant.slug == default_tenant_slug).first()
        if tenant is None:
            tenant = Tenant(name=default_tenant_name, slug=default_tenant_slug)
            db.add(tenant)
            db.flush()
            created_tenant = True

        user = (
            db.query(User)
            .filter(User.email == default_admin_email, User.tenant_id == tenant.id)
            .first()
        )
        if user is None:
            user = User(
                tenant_id=tenant.id,
                email=default_admin_email,
                username=default_admin_username,
                hashed_password=hash_password(default_admin_password),
                is_admin=True,
                is_active=True,
            )
            db.add(user)
            db.flush()
            created_user = True

        tenant_user = (
            db.query(TenantUser)
            .filter(TenantUser.user_id == user.id, TenantUser.tenant_id == tenant.id)
            .first()
        )
        if tenant_user is None:
            tenant_user = TenantUser(
                user_id=user.id,
                tenant_id=tenant.id,
                role=UserRole.OWNER,
                is_active=True,
            )
            db.add(tenant_user)
        else:
            tenant_user.role = UserRole.OWNER
            tenant_user.is_active = True

        db.commit()
        db.refresh(tenant)
        db.refresh(user)
        return tenant, user, created_tenant, created_user, default_admin_password
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def verify_tables_exist() -> list[str]:
    """Verify core tables exist after initialization."""
    inspector = inspect(engine)
    existing = set(inspector.get_table_names())
    expected = {
        "tenants",
        "users",
        "agents",
        "agent_executions",
        "execution_logs",
        "agent_usage",
        "tenant_subscriptions",
        "tenant_users",
        "audit_logs",
    }
    return sorted(expected - existing)


def main() -> None:
    print("[init] Starting database initialization...")

    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))

    run_migrations_or_create_tables()
    initialize_application()

    if _bool_from_env("BOOTSTRAP_DEFAULT_ADMIN", True):
        tenant, user, created_tenant, created_user, password = ensure_default_tenant_and_admin()
        print(f"[init] Tenant: {tenant.slug} ({'created' if created_tenant else 'existing'})")
        print(f"[init] Admin user: {user.email} ({'created' if created_user else 'existing'})")
        if created_user:
            print(f"[init] Admin password (first run): {password}")

    missing = verify_tables_exist()
    if missing:
        raise RuntimeError(f"Missing expected tables after initialization: {missing}")

    print("[init] Database initialization completed successfully.")
    print("[init] Login: POST /api/auth/login?tenant_slug=default")
    print("[init] Username/email: admin@example.com")


if __name__ == "__main__":
    main()
