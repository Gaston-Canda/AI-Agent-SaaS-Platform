"""Tenant isolation guard helpers."""

from __future__ import annotations

from fastapi import HTTPException, status


def enforce_tenant_match(resource_tenant_id: str | None, jwt_tenant_id: str, resource_name: str = "resource") -> None:
    """Ensure resource belongs to authenticated tenant."""
    if not resource_tenant_id or resource_tenant_id != jwt_tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Cross-tenant access denied for {resource_name}",
        )
