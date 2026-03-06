"""Database Query Tool - allows agents to query PostgreSQL."""
from typing import Optional, List, Dict, Any
from app.tools.base_tool import BaseTool, ToolOutput
from app.db.database import SessionLocal


class DatabaseQueryTool(BaseTool):
    """Tool for querying PostgreSQL database."""

    def __init__(self):
        """Initialize database query tool."""
        super().__init__(
            name="database_query",
            description="Execute read-only SQL queries against PostgreSQL database"
        )
        self._allowed_operations = ["SELECT"]
        self._max_rows = 100

    def get_schema(self) -> dict:
        """Get JSON schema for database query inputs."""
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "SQL query (SELECT only, read-only operations)"
                },
                "max_rows": {
                    "type": "integer",
                    "description": "Maximum number of rows to return (default: 100)",
                    "minimum": 1,
                    "maximum": 1000
                }
            },
            "required": ["query"]
        }

    async def execute(
        self,
        query: str,
        max_rows: int = 100,
        **kwargs
    ) -> ToolOutput:
        """
        Execute database query.
        
        Args:
            query: SQL SELECT query
            max_rows: Maximum rows to return
            
        Returns:
            ToolOutput with query results or error
        """
        try:
            # Validate query
            query_upper = query.strip().upper()
            
            # Only allow SELECT queries (read-only)
            if not query_upper.startswith("SELECT"):
                return ToolOutput(
                    success=False,
                    result=None,
                    error="Only SELECT queries are allowed (read-only operations)"
                )
            
            # Check for dangerous keywords
            dangerous_keywords = ["DROP", "DELETE", "UPDATE", "INSERT", "TRUNCATE", "ALTER"]
            for keyword in dangerous_keywords:
                if keyword in query_upper:
                    return ToolOutput(
                        success=False,
                        result=None,
                        error=f"Operation containing '{keyword}' is not allowed"
                    )
            
            # Limit max_rows
            if max_rows > self._max_rows:
                max_rows = self._max_rows
            
            # Execute query
            db = SessionLocal()
            try:
                # Use raw SQL
                result = db.execute(query)
                rows = result.fetchmany(max_rows)
                
                # Convert rows to list of dicts
                if rows:
                    # Get column names
                    columns = result.keys()
                    data = [dict(zip(columns, row)) for row in rows]
                else:
                    data = []
                
                # Check if there are more rows
                has_more = len(rows) == max_rows
                
                db.close()
                
                return ToolOutput(
                    success=True,
                    result={
                        "rows": data,
                        "row_count": len(data),
                        "has_more_rows": has_more,
                        "max_rows_returned": max_rows
                    }
                )
            except Exception as query_error:
                db.close()
                raise query_error
            
        except Exception as e:
            return ToolOutput(
                success=False,
                result=None,
                error=f"Database error: {str(e)}"
            )
