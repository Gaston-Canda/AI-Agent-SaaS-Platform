"""Base memory class."""
from abc import ABC, abstractmethod
from typing import Any, Optional, List
from datetime import datetime
from pydantic import BaseModel


class MemoryMessage(BaseModel):
    """A message in memory."""
    role: str  # "user" or "assistant"
    content: str
    timestamp: datetime
    metadata: Optional[dict] = None


class BaseMemory(ABC):
    """
    Abstract base class for memory systems.
    
    Memory allows agents to maintain state across interactions.
    - Conversation Memory: short-term, recent messages
    - Vector Memory: long-term, semantic search
    """

    def __init__(self, memory_id: str, max_size: int = 1000):
        """
        Initialize memory.
        
        Args:
            memory_id: Unique identifier for this memory
            max_size: Maximum number of items to store
        """
        self.memory_id = memory_id
        self.max_size = max_size
        self.created_at = datetime.now()

    @abstractmethod
    async def add_message(self, role: str, content: str, metadata: Optional[dict] = None) -> None:
        """
        Add a message to memory.
        
        Args:
            role: "user" or "assistant"
            content: Message content
            metadata: Optional metadata
        """
        pass

    @abstractmethod
    async def get_messages(self, limit: int = None) -> List[MemoryMessage]:
        """
        Get messages from memory.
        
        Args:
            limit: Maximum number of messages to return
            
        Returns:
            List of MemoryMessage objects
        """
        pass

    @abstractmethod
    async def search(self, query: str, limit: int = 10) -> List[MemoryMessage]:
        """
        Search memory for relevant messages.
        
        Args:
            query: Search query
            limit: Maximum results
            
        Returns:
            List of matching MemoryMessage objects
        """
        pass

    @abstractmethod
    async def clear(self) -> None:
        """Clear all messages from memory."""
        pass

    @abstractmethod
    async def get_summary(self) -> str:
        """
        Get a summary of memory contents.
        
        Useful for fitting memory into context window.
        
        Returns:
            Summary string
        """
        pass

    def get_info(self) -> dict:
        """Get memory information."""
        return {
            "memory_id": self.memory_id,
            "created_at": self.created_at.isoformat(),
            "max_size": self.max_size
        }
