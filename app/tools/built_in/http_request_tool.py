"""HTTP Request Tool - allows agents to make HTTP requests."""
from typing import Optional
import httpx
from app.tools.base_tool import BaseTool, ToolOutput


class HTTPRequestTool(BaseTool):
    """
    Tool for making HTTP requests.
    
    Allows agents to fetch data from external APIs.
    """

    def __init__(self, timeout: int = 30, max_response_size: int = 10000):
        """
        Initialize HTTP tool.
        
        Args:
            timeout: Request timeout in seconds
            max_response_size: Max response body size in bytes
        """
        super().__init__(
            name="http_request",
            description="Make HTTP requests to external APIs and websites"
        )
        self.timeout = timeout
        self.max_response_size = max_response_size

    def get_schema(self) -> dict:
        """Get JSON schema for HTTP request inputs."""
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The URL to request"
                },
                "method": {
                    "type": "string",
                    "enum": ["GET", "POST", "PUT", "DELETE"],
                    "description": "HTTP method"
                },
                "headers": {
                    "type": "object",
                    "description": "HTTP headers as key-value pairs",
                    "additionalProperties": {"type": "string"}
                },
                "body": {
                    "type": "string",
                    "description": "Request body for POST/PUT"
                }
            },
            "required": ["url", "method"]
        }

    async def execute(
        self,
        url: str,
        method: str = "GET",
        headers: Optional[dict] = None,
        body: Optional[str] = None,
        **kwargs
    ) -> ToolOutput:
        """
        Execute HTTP request.
        
        Args:
            url: URL to request
            method: HTTP method
            headers: HTTP headers
            body: Request body
            
        Returns:
            ToolOutput with response or error
        """
        try:
            # Validate URL
            if not url.startswith(("http://", "https://")):
                return ToolOutput(
                    success=False,
                    result=None,
                    error="URL must start with http:// or https://"
                )
            
            # Default headers
            request_headers = headers or {}
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.request(
                    method=method.upper(),
                    url=url,
                    headers=request_headers,
                    content=body.encode() if body else None
                )
                
                # Get response content (limited size)
                content = response.text[:self.max_response_size]
                
                return ToolOutput(
                    success=True,
                    result={
                        "status_code": response.status_code,
                        "headers": dict(response.headers),
                        "body": content,
                        "truncated": len(response.text) > self.max_response_size
                    }
                )
        
        except httpx.RequestError as e:
            return ToolOutput(
                success=False,
                result=None,
                error=f"HTTP request error: {str(e)}"
            )
        except Exception as e:
            return ToolOutput(
                success=False,
                result=None,
                error=f"Unexpected error: {str(e)}"
            )
