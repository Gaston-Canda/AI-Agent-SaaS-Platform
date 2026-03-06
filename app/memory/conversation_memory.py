"""Conversation Memory - short-term memory using Redis."""
import json
from typing import Optional, List
from datetime import datetime
import redis.asyncio as redis
from app.memory.base_memory import BaseMemory, MemoryMessage
from app.core.config import settings


class ConversationMemory(BaseMemory):
    """
    Short-term conversation memory backed by Redis.
    
    Stores recent messages from conversations for context.
    Ideal for multi-turn interactions where recent context is important.
    """

    def __init__(self, memory_id: str, max_size: int = 100, redis_client: Optional[redis.Redis] = None):
        """
        Initialize conversation memory.
        
        Args:
            memory_id: Unique ID for this memory (e.g., conversation_id)
            max_size: Max messages to keep (FIFO)
            redis_client: Redis client (created if not provided)
        """
        super().__init__(memory_id=memory_id, max_size=max_size)
        self.redis_client = redis_client
        self.key = f"memory:conversation:{memory_id}"

    async def _get_redis(self) -> redis.Redis:
        """Get or create Redis client."""
        if not self.redis_client:
            self.redis_client = await redis.from_url(
                settings.REDIS_URL,
                decode_responses=True
            )
        return self.redis_client

    async def add_message(self, role: str, content: str, metadata: Optional[dict] = None) -> None:
        """Add message to conversation memory."""
        redis_client = await self._get_redis()
        
        message = MemoryMessage(
            role=role,
            content=content,
            timestamp=datetime.now(),
            metadata=metadata
        )
        
        # Store as JSON in Redis list
        await redis_client.rpush(
            self.key,
            json.dumps(message.model_dump(mode='json'))
        )
        
        # Keep only max_size messages (FIFO)
        await redis_client.ltrim(self.key, -self.max_size, -1)
        
        # Set expiry (7 days)
        await redis_client.expire(self.key, 7 * 24 * 60 * 60)

    async def get_messages(self, limit: int = None) -> List[MemoryMessage]:
        """Get recent messages from memory."""
        redis_client = await self._get_redis()
        
        # Get all or last N messages
        if limit:
            messages_json = await redis_client.lrange(self.key, -limit, -1)
        else:
            messages_json = await redis_client.lrange(self.key, 0, -1)
        
        messages = []
        for msg_json in messages_json:
            msg_dict = json.loads(msg_json)
            msg_dict['timestamp'] = datetime.fromisoformat(msg_dict['timestamp'])
            messages.append(MemoryMessage(**msg_dict))
        
        return messages

    async def search(self, query: str, limit: int = 10) -> List[MemoryMessage]:
        """
        Search memory using string matching.
        
        Note: For semantic search, use VectorMemory.
        This is simple substring matching.
        """
        messages = await self.get_messages()
        
        # Simple substring search
        results = [
            msg for msg in messages
            if query.lower() in msg.content.lower()
        ]
        
        # Return most recent matches
        return results[-limit:] if results else []

    async def get_summary(self) -> str:
        """Get summary of conversation memory."""
        messages = await self.get_messages()
        
        if not messages:
            return "No conversation history."
        
        summary_lines = []
        for msg in messages:
            role = msg.role.upper()
            preview = msg.content[:100]
            if len(msg.content) > 100:
                preview += "..."
            summary_lines.append(f"{role}: {preview}")
        
        return "\n".join(summary_lines)

    async def clear(self) -> None:
        """Clear conversation memory."""
        redis_client = await self._get_redis()
        await redis_client.delete(self.key)

    async def count_messages(self) -> int:
        """Count messages in memory."""
        redis_client = await self._get_redis()
        return await redis_client.llen(self.key)

    async def get_context_window(self, max_tokens: int = 2000) -> str:
        """
        Get messages that fit within token limit for LLM context.
        
        Args:
            max_tokens: Target token count
            
        Returns:
            Formatted string of messages
        """
        messages = await self.get_messages()
        
        # Approximate: 4 chars = 1 token
        token_budget = max_tokens * 4
        context = ""
        token_count = 0
        
        # Add messages from most recent (backwards)
        for msg in reversed(messages):
            msg_text = f"{msg.role.upper()}:\n{msg.content}\n\n"
            msg_tokens = len(msg_text) // 4
            
            if token_count + msg_tokens > token_budget:
                break
            
            context = msg_text + context
            token_count += msg_tokens
        
        return context
