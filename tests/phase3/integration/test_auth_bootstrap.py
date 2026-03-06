"""Integration tests for multi-tenant bootstrap in auth registration."""

import uuid

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base, get_db
from app.models.extended import TenantUser, UserRole
from app.models.user import Tenant
from app.routers.auth import router as auth_router


def test_register_bootstraps_tenant_and_owner_role(monkeypatch) -> None:
    """Flow 1: first register should create tenant and owner user."""
    engine = create_engine("sqlite:///test_auth_bootstrap.db", connect_args={"check_same_thread": False})
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    app = FastAPI()
    app.include_router(auth_router)

    monkeypatch.setattr("app.services.user_service.hash_password", lambda password: f"hashed::{password}")
    monkeypatch.setattr(
        "app.services.user_service.verify_password",
        lambda plain_password, hashed_password: hashed_password == f"hashed::{plain_password}",
    )

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    register_payload_1 = {
        "email": f"owner-{uuid.uuid4().hex[:8]}@example.com",
        "username": "owner_user",
        "password": "securepass123",
    }
    tenant_slug = f"origen-{uuid.uuid4().hex[:8]}"
    response_1 = client.post(f"/api/auth/register?tenant_slug={tenant_slug}", json=register_payload_1)
    assert response_1.status_code == 200
    data_1 = response_1.json()
    assert data_1["token_type"] == "bearer"
    assert data_1["user"]["tenant_id"]

    verify_db = SessionLocal()
    tenant = verify_db.query(Tenant).filter(Tenant.slug == tenant_slug).first()
    assert tenant is not None

    owner_link = verify_db.query(TenantUser).filter(
        TenantUser.user_id == data_1["user"]["id"],
        TenantUser.tenant_id == tenant.id,
    ).first()
    assert owner_link is not None
    assert owner_link.role == UserRole.OWNER

    # Flow 2: second register should reuse tenant and add member
    register_payload_2 = {
        "email": f"member-{uuid.uuid4().hex[:8]}@example.com",
        "username": "member_user",
        "password": "securepass123",
    }
    response_2 = client.post(f"/api/auth/register?tenant_slug={tenant_slug}", json=register_payload_2)
    assert response_2.status_code == 200
    data_2 = response_2.json()
    assert data_2["user"]["tenant_id"] == tenant.id

    tenant_count = verify_db.query(Tenant).filter(Tenant.slug == tenant_slug).count()
    assert tenant_count == 1

    member_link = verify_db.query(TenantUser).filter(
        TenantUser.user_id == data_2["user"]["id"],
        TenantUser.tenant_id == tenant.id,
    ).first()
    assert member_link is not None
    assert member_link.role == UserRole.MEMBER

    # Flow 3: login returns JWT tokens
    login_response = client.post(
        f"/api/auth/login?tenant_slug={tenant_slug}",
        json={"email": register_payload_1["email"], "password": register_payload_1["password"]},
    )
    assert login_response.status_code == 200
    login_data = login_response.json()
    assert login_data["access_token"]
    assert login_data["refresh_token"]
    assert login_data["token_type"] == "bearer"

    verify_db.close()
