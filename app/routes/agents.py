"""
API routes for agent management (Phase 3).

This module provides REST endpoints for:
- Agent CRUD operations
- Agent versioning
- Tool configuration
- Prompt configuration
- Agent loading (pre-execution validation)

All endpoints require JWT authentication. Tenant ID is extracted from token
for mandatory multi-tenancy filtering on every operation.
"""

from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import verify_token, TokenData
from app.agents import (
    AgentService,
    AgentVersionService,
    AgentToolService,
    AgentPromptService,
    AgentLoader,
    get_agent_loader,
    AgentResponse,
    CreateAgentRequest,
    UpdateAgentRequest,
    ListAgentsResponse,
    AgentVersionResponse,
    CreateVersionRequest,
    ListVersionsResponse,
    AgentToolResponse,
    AddToolRequest,
    UpdateToolConfigRequest,
    ListAgentToolsResponse,
    AgentPromptResponse,
    CreatePromptRequest,
    UpdatePromptRequest,
    ListAgentPromptsResponse,
    AgentConfig,
)
from app.core.exceptions import (
    ResourceNotFoundError,
    ValidationError,
    PermissionDeniedError,
    ConflictError,
)

router = APIRouter(prefix="/agents", tags=["agents"])


# ============================================================================
# Dependency: Extract tenant from JWT token
# ============================================================================

async def get_current_user(token: str = None) -> TokenData:
    """
    Extract and validate JWT token from Authorization header.
    
    The token should be passed via Depends(get_token_from_header) in each route.
    This is a placeholder - actual implementation uses FastAPI Security.
    """
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization token",
        )
    
    try:
        token_data = verify_token(token)
        return token_data
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}",
        )


# ============================================================================
# AGENT CRUD ENDPOINTS
# ============================================================================

@router.post(
    "",
    response_model=AgentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new agent",
)
async def create_agent(
    request: CreateAgentRequest,
    db: AsyncSession = Depends(get_db),
    token_data: TokenData = Depends(get_current_user),
) -> AgentResponse:
    """
    Create a new agent.
    
    **Authentication**: Required (JWT token)
    
    **Multi-tenancy**: Agent is created for the tenant in the JWT token
    
    **Request**:
    ```json
    {
        "name": "Customer Support Agent",
        "description": "Handles customer inquiries",
        "config": {"key": "value"}
    }
    ```
    
    **Response**: AgentResponse with agent_id, created_at, etc.
    
    **Errors**:
    - 400: Invalid request data
    - 401: Unauthorized (missing/invalid token)
    - 409: Agent name already exists for tenant
    """
    try:
        service = AgentService()
        agent = await service.create_agent(
            db=db,
            tenant_id=token_data.tenant_id,
            name=request.name,
            description=request.description,
            config=request.config,
        )
        return agent
    except ConflictError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get(
    "",
    response_model=ListAgentsResponse,
    summary="List agents for tenant",
)
async def list_agents(
    skip: int = 0,
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
    token_data: TokenData = Depends(get_current_user),
) -> ListAgentsResponse:
    """
    List all agents for the current tenant.
    
    **Authentication**: Required
    
    **Pagination**: skip/limit (max limit=100)
    
    **Query Parameters**:
    - skip: Number of records to skip (default: 0)
    - limit: Number of records to return (default: 10, max: 100)
    
    **Response**: ListAgentsResponse with items and total count
    """
    try:
        service = AgentService()
        result = await service.list_agents(
            db=db,
            tenant_id=token_data.tenant_id,
            skip=skip,
            limit=min(limit, 100),
        )
        return result
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get(
    "/{agent_id}",
    response_model=AgentResponse,
    summary="Get agent by ID",
)
async def get_agent(
    agent_id: str,
    db: AsyncSession = Depends(get_db),
    token_data: TokenData = Depends(get_current_user),
) -> AgentResponse:
    """
    Get a single agent by ID.
    
    **Authentication**: Required
    
    **Path Parameters**:
    - agent_id: Agent ID
    
    **Response**: AgentResponse with all agent details
    
    **Errors**:
    - 404: Agent not found
    - 403: Agent belongs to different tenant
    """
    try:
        service = AgentService()
        agent = await service.get_agent(
            db=db,
            agent_id=agent_id,
            tenant_id=token_data.tenant_id,
        )
        return agent
    except ResourceNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except PermissionDeniedError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )


@router.put(
    "/{agent_id}",
    response_model=AgentResponse,
    summary="Update an agent",
)
async def update_agent(
    agent_id: str,
    request: UpdateAgentRequest,
    db: AsyncSession = Depends(get_db),
    token_data: TokenData = Depends(get_current_user),
) -> AgentResponse:
    """
    Update an agent.
    
    **Authentication**: Required
    
    **Path Parameters**:
    - agent_id: Agent ID
    
    **Request**: UpdateAgentRequest (name, description, config are optional)
    
    **Response**: Updated AgentResponse
    
    **Errors**:
    - 404: Agent not found
    - 403: Agent belongs to different tenant
    - 409: Name already exists
    """
    try:
        service = AgentService()
        agent = await service.update_agent(
            db=db,
            agent_id=agent_id,
            tenant_id=token_data.tenant_id,
            name=request.name,
            description=request.description,
            config=request.config,
        )
        return agent
    except ResourceNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except PermissionDeniedError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )
    except ConflictError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )


@router.delete(
    "/{agent_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an agent",
)
async def delete_agent(
    agent_id: str,
    db: AsyncSession = Depends(get_db),
    token_data: TokenData = Depends(get_current_user),
) -> None:
    """
    Delete an agent (soft delete - archives the agent).
    
    **Authentication**: Required
    
    **Path Parameters**:
    - agent_id: Agent ID
    
    **Response**: 204 No Content
    
    **Errors**:
    - 404: Agent not found
    - 403: Agent belongs to different tenant
    """
    try:
        service = AgentService()
        await service.delete_agent(
            db=db,
            agent_id=agent_id,
            tenant_id=token_data.tenant_id,
        )
    except ResourceNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except PermissionDeniedError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )


# ============================================================================
# AGENT VERSION ENDPOINTS
# ============================================================================

@router.post(
    "/{agent_id}/versions",
    response_model=AgentVersionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new agent version",
)
async def create_version(
    agent_id: str,
    request: CreateVersionRequest,
    db: AsyncSession = Depends(get_db),
    token_data: TokenData = Depends(get_current_user),
) -> AgentVersionResponse:
    """
    Create a new version for an agent.
    
    **Authentication**: Required
    
    **Path Parameters**:
    - agent_id: Agent ID
    
    **Request**:
    ```json
    {
        "system_prompt": "You are a helpful assistant",
        "configuration": {
            "llm_config": {
                "provider": "openai",
                "model": "gpt-4",
                "temperature": 0.7,
                "max_tokens": 2048
            },
            "memory_config": {
                "type": "conversation",
                "max_history": 10
            }
        }
    }
    ```
    
    **Response**: AgentVersionResponse with auto-incremented version number
    
    **Errors**:
    - 404: Agent not found
    - 403: Agent belongs to different tenant
    - 422: Invalid configuration
    """
    try:
        service = AgentVersionService()
        version = await service.create_version(
            db=db,
            agent_id=agent_id,
            tenant_id=token_data.tenant_id,
            system_prompt=request.system_prompt,
            configuration=request.configuration,
        )
        return version
    except ResourceNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except PermissionDeniedError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )


@router.get(
    "/{agent_id}/versions",
    response_model=ListVersionsResponse,
    summary="List versions for agent",
)
async def list_versions(
    agent_id: str,
    skip: int = 0,
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
    token_data: TokenData = Depends(get_current_user),
) -> ListVersionsResponse:
    """
    List all versions for an agent.
    
    **Authentication**: Required
    
    **Path Parameters**:
    - agent_id: Agent ID
    
    **Query Parameters**:
    - skip: Number of records to skip (default: 0)
    - limit: Number of records to return (default: 10, max: 100)
    
    **Response**: ListVersionsResponse with versions and total count
    """
    try:
        service = AgentVersionService()
        result = await service.get_versions(
            db=db,
            agent_id=agent_id,
            tenant_id=token_data.tenant_id,
            skip=skip,
            limit=min(limit, 100),
        )
        return result
    except ResourceNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except PermissionDeniedError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )


@router.post(
    "/{agent_id}/versions/{version_id}/activate",
    response_model=AgentVersionResponse,
    summary="Activate a version",
)
async def activate_version(
    agent_id: str,
    version_id: str,
    db: AsyncSession = Depends(get_db),
    token_data: TokenData = Depends(get_current_user),
) -> AgentVersionResponse:
    """
    Activate a specific version (make it the active version).
    
    **Authentication**: Required
    
    **Path Parameters**:
    - agent_id: Agent ID
    - version_id: Version ID to activate
    
    **Response**: Updated AgentVersionResponse with is_active=True
    
    **Behavior**:
    - Deactivates current active version
    - Activates specified version
    - Validates configuration before activation
    
    **Errors**:
    - 404: Agent or version not found
    - 403: Permission denied
    - 422: Invalid configuration
    """
    try:
        service = AgentVersionService()
        version = await service.activate_version(
            db=db,
            agent_id=agent_id,
            version_id=version_id,
            tenant_id=token_data.tenant_id,
        )
        return version
    except ResourceNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except PermissionDeniedError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )


@router.post(
    "/{agent_id}/versions/{version_id}/rollback",
    response_model=AgentVersionResponse,
    summary="Rollback to previous version",
)
async def rollback_version(
    agent_id: str,
    version_id: str,
    db: AsyncSession = Depends(get_db),
    token_data: TokenData = Depends(get_current_user),
) -> AgentVersionResponse:
    """
    Rollback to a previous version.
    
    **Authentication**: Required
    
    **Path Parameters**:
    - agent_id: Agent ID
    - version_id: Version ID to rollback to
    
    **Response**: AgentVersionResponse with is_active=True
    
    **Behavior**:
    - Marks current version as inactive
    - Activates previous version
    - Useful for A/B testing or incident recovery
    
    **Errors**:
    - 404: Agent or version not found
    - 403: Permission denied
    """
    try:
        service = AgentVersionService()
        version = await service.rollback_version(
            db=db,
            agent_id=agent_id,
            version_id=version_id,
            tenant_id=token_data.tenant_id,
        )
        return version
    except ResourceNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except PermissionDeniedError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )


# ============================================================================
# AGENT TOOL ENDPOINTS
# ============================================================================

@router.post(
    "/{agent_id}/versions/{version_id}/tools",
    response_model=AgentToolResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a tool to version",
)
async def add_tool(
    agent_id: str,
    version_id: str,
    request: AddToolRequest,
    db: AsyncSession = Depends(get_db),
    token_data: TokenData = Depends(get_current_user),
) -> AgentToolResponse:
    """
    Add a tool to an agent version.
    
    **Authentication**: Required
    
    **Path Parameters**:
    - agent_id: Agent ID
    - version_id: Version ID
    
    **Request**:
    ```json
    {
        "tool_name": "google_search",
        "tool_config": {
            "timeout": 30,
            "max_results": 5
        }
    }
    ```
    
    **Validation**: Tool must exist in global ToolRegistry
    
    **Response**: AgentToolResponse
    
    **Errors**:
    - 404: Agent, version, or tool not found
    - 403: Permission denied
    - 409: Tool already added to version
    - 422: Tool not in ToolRegistry
    """
    try:
        service = AgentToolService()
        tool = await service.add_tool_to_version(
            db=db,
            agent_id=agent_id,
            version_id=version_id,
            tenant_id=token_data.tenant_id,
            tool_name=request.tool_name,
            tool_config=request.tool_config,
        )
        return tool
    except ResourceNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except PermissionDeniedError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )
    except ConflictError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )


@router.get(
    "/{agent_id}/versions/{version_id}/tools",
    response_model=ListAgentToolsResponse,
    summary="List tools for version",
)
async def list_tools(
    agent_id: str,
    version_id: str,
    enabled_only: bool = False,
    skip: int = 0,
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
    token_data: TokenData = Depends(get_current_user),
) -> ListAgentToolsResponse:
    """
    List tools for an agent version.
    
    **Authentication**: Required
    
    **Path Parameters**:
    - agent_id: Agent ID
    - version_id: Version ID
    
    **Query Parameters**:
    - enabled_only: Show only enabled tools (default: False)
    - skip: Number of records to skip (default: 0)
    - limit: Number of records to return (default: 10, max: 100)
    
    **Response**: ListAgentToolsResponse with tools and total count
    """
    try:
        service = AgentToolService()
        result = await service.get_tools_for_version(
            db=db,
            agent_id=agent_id,
            version_id=version_id,
            tenant_id=token_data.tenant_id,
            enabled_only=enabled_only,
            skip=skip,
            limit=min(limit, 100),
        )
        return result
    except ResourceNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except PermissionDeniedError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )


@router.delete(
    "/{agent_id}/versions/{version_id}/tools/{tool_name}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a tool from version",
)
async def remove_tool(
    agent_id: str,
    version_id: str,
    tool_name: str,
    db: AsyncSession = Depends(get_db),
    token_data: TokenData = Depends(get_current_user),
) -> None:
    """
    Remove a tool from an agent version (hard delete).
    
    **Authentication**: Required
    
    **Path Parameters**:
    - agent_id: Agent ID
    - version_id: Version ID
    - tool_name: Name of tool to remove
    
    **Response**: 204 No Content
    
    **Errors**:
    - 404: Agent, version, or tool not found
    - 403: Permission denied
    """
    try:
        service = AgentToolService()
        await service.remove_tool_from_version(
            db=db,
            agent_id=agent_id,
            version_id=version_id,
            tenant_id=token_data.tenant_id,
            tool_name=tool_name,
        )
    except ResourceNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except PermissionDeniedError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )


@router.patch(
    "/{agent_id}/versions/{version_id}/tools/{tool_name}",
    response_model=AgentToolResponse,
    summary="Update tool configuration",
)
async def update_tool_config(
    agent_id: str,
    version_id: str,
    tool_name: str,
    request: UpdateToolConfigRequest,
    db: AsyncSession = Depends(get_db),
    token_data: TokenData = Depends(get_current_user),
) -> AgentToolResponse:
    """
    Update tool configuration (enable/disable or change settings).
    
    **Authentication**: Required
    
    **Path Parameters**:
    - agent_id: Agent ID
    - version_id: Version ID
    - tool_name: Name of tool to update
    
    **Request**:
    ```json
    {
        "enabled": true,
        "tool_config": {
            "timeout": 60,
            "max_results": 10
        }
    }
    ```
    
    **Response**: Updated AgentToolResponse
    
    **Errors**:
    - 404: Agent, version, or tool not found
    - 403: Permission denied
    - 422: Invalid configuration
    """
    try:
        service = AgentToolService()
        tool = await service.update_tool_config(
            db=db,
            agent_id=agent_id,
            version_id=version_id,
            tenant_id=token_data.tenant_id,
            tool_name=tool_name,
            enabled=request.enabled,
            tool_config=request.tool_config,
        )
        return tool
    except ResourceNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except PermissionDeniedError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )


# ============================================================================
# AGENT PROMPT ENDPOINTS
# ============================================================================

@router.post(
    "/{agent_id}/versions/{version_id}/prompts",
    response_model=AgentPromptResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a prompt for version",
)
async def create_prompt(
    agent_id: str,
    version_id: str,
    request: CreatePromptRequest,
    db: AsyncSession = Depends(get_db),
    token_data: TokenData = Depends(get_current_user),
) -> AgentPromptResponse:
    """
    Create a prompt for an agent version.
    
    **Authentication**: Required
    
    **Path Parameters**:
    - agent_id: Agent ID
    - version_id: Version ID
    
    **Request**:
    ```json
    {
        "prompt_type": "system",
        "prompt_content": "You are a helpful customer support agent..."
    }
    ```
    
    **Constraint**: Only ONE prompt per type per version (unique constraint)
    
    **Valid Types**: "system", "instruction", "context", "fallback"
    
    **Response**: AgentPromptResponse
    
    **Errors**:
    - 404: Agent or version not found
    - 403: Permission denied
    - 409: Prompt of this type already exists for version
    - 422: Invalid prompt type or missing content
    """
    try:
        service = AgentPromptService()
        prompt = await service.create_prompt(
            db=db,
            agent_id=agent_id,
            version_id=version_id,
            tenant_id=token_data.tenant_id,
            prompt_type=request.prompt_type,
            prompt_content=request.prompt_content,
            created_by=token_data.user_id,
        )
        return prompt
    except ResourceNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except PermissionDeniedError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )
    except ConflictError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )


@router.get(
    "/{agent_id}/versions/{version_id}/prompts",
    response_model=ListAgentPromptsResponse,
    summary="List prompts for version",
)
async def list_prompts(
    agent_id: str,
    version_id: str,
    skip: int = 0,
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
    token_data: TokenData = Depends(get_current_user),
) -> ListAgentPromptsResponse:
    """
    List all prompts for an agent version.
    
    **Authentication**: Required
    
    **Path Parameters**:
    - agent_id: Agent ID
    - version_id: Version ID
    
    **Query Parameters**:
    - skip: Number of records to skip (default: 0)
    - limit: Number of records to return (default: 10, max: 100)
    
    **Response**: ListAgentPromptsResponse with prompts and total count
    """
    try:
        service = AgentPromptService()
        result = await service.list_prompts(
            db=db,
            agent_id=agent_id,
            version_id=version_id,
            tenant_id=token_data.tenant_id,
            skip=skip,
            limit=min(limit, 100),
        )
        return result
    except ResourceNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except PermissionDeniedError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )


@router.put(
    "/{agent_id}/versions/{version_id}/prompts/{prompt_type}",
    response_model=AgentPromptResponse,
    summary="Update a prompt",
)
async def update_prompt(
    agent_id: str,
    version_id: str,
    prompt_type: str,
    request: UpdatePromptRequest,
    db: AsyncSession = Depends(get_db),
    token_data: TokenData = Depends(get_current_user),
) -> AgentPromptResponse:
    """
    Update a prompt by type.
    
    **Authentication**: Required
    
    **Path Parameters**:
    - agent_id: Agent ID
    - version_id: Version ID
    - prompt_type: Prompt type ("system", "instruction", "context", "fallback")
    
    **Request**:
    ```json
    {
        "prompt_content": "Updated prompt content..."
    }
    ```
    
    **Response**: Updated AgentPromptResponse
    
    **Errors**:
    - 404: Agent, version, or prompt not found
    - 403: Permission denied
    - 422: Invalid prompt type
    """
    try:
        service = AgentPromptService()
        prompt = await service.update_prompt(
            db=db,
            agent_id=agent_id,
            version_id=version_id,
            tenant_id=token_data.tenant_id,
            prompt_type=prompt_type,
            prompt_content=request.prompt_content,
        )
        return prompt
    except ResourceNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except PermissionDeniedError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )


@router.delete(
    "/{agent_id}/versions/{version_id}/prompts/{prompt_type}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a prompt",
)
async def delete_prompt(
    agent_id: str,
    version_id: str,
    prompt_type: str,
    db: AsyncSession = Depends(get_db),
    token_data: TokenData = Depends(get_current_user),
) -> None:
    """
    Delete a prompt by type.
    
    **Authentication**: Required
    
    **Path Parameters**:
    - agent_id: Agent ID
    - version_id: Version ID
    - prompt_type: Prompt type ("system", "instruction", "context", "fallback")
    
    **Response**: 204 No Content
    
    **Note**: System prompt cannot be deleted (required)
    
    **Errors**:
    - 404: Agent, version, or prompt not found
    - 403: Permission denied
    - 422: Cannot delete system prompt
    """
    try:
        service = AgentPromptService()
        await service.delete_prompt(
            db=db,
            agent_id=agent_id,
            version_id=version_id,
            tenant_id=token_data.tenant_id,
            prompt_type=prompt_type,
        )
    except ResourceNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except PermissionDeniedError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )


# ============================================================================
# AGENT LOADING ENDPOINT (Pre-execution validation)
# ============================================================================

@router.post(
    "/{agent_id}/load",
    response_model=AgentConfig,
    summary="Load complete agent configuration",
)
async def load_agent_config(
    agent_id: str,
    db: AsyncSession = Depends(get_db),
    token_data: TokenData = Depends(get_current_user),
) -> AgentConfig:
    """
    Load complete agent configuration for execution.
    
    **Authentication**: Required
    
    **Path Parameters**:
    - agent_id: Agent ID
    
    **Response**: AgentConfig with complete runtime configuration
    
    **Description**:
    This endpoint orchestrates loading the agent's:
    - Active version
    - All prompts (system, instruction, context, fallback)
    - All enabled tools
    - LLM configuration
    - Memory configuration
    
    The returned AgentConfig can be passed directly to AgentEngine.execute()
    
    **ValidationSteps**:
    1. ✅ Agent exists and belongs to tenant
    2. ✅ Active version exists
    3. ✅ System prompt present
    4. ✅ All tools exist in ToolRegistry
    5. ✅ LLM configuration is complete
    
    **Example Response**:
    ```json
    {
        "agent_id": "agent_123abc",
        "version_number": "1.1",
        "system_prompt": "[SYSTEM]\\nYou are...",
        "prompts": {
            "system": "You are...",
            "instruction": "Be brief...",
            "context": null,
            "fallback": null
        },
        "llm_config": {
            "provider": "openai",
            "model": "gpt-4-turbo-preview",
            "temperature": 0.7,
            "max_tokens": 2048
        },
        "tools": [
            {
                "name": "google_search",
                "enabled": true,
                "config": {"timeout": 30}
            }
        ],
        "memory_config": {
            "type": "conversation",
            "max_history": 10,
            "enable_vector": false
        }
    }
    ```
    
    **Errors**:
    - 404: Agent not found
    - 403: Agent belongs to different tenant
    - 422: Configuration validation failed (missing version, prompts, etc.)
    """
    try:
        loader = get_agent_loader()
        config = await loader.load_agent(
            db=db,
            agent_id=agent_id,
            tenant_id=token_data.tenant_id,
        )
        return config
    except ResourceNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except PermissionDeniedError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )
    except ConflictError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )
