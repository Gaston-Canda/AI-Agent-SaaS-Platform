"""Memory Manager - coordinates conversation and vector memory."""
from typing import Optional, List
from app.memory.base_memory import BaseMemory, MemoryMessage
from app.memory.conversation_memory import ConversationMemory
from app.memory.vector_memory import VectorMemory


class MemoryManager:
    """
    Centralized memory management for agents.
    
    - Conversation Memory: Recent messages for LLM context
    - Vector Memory: Long-term storage with semantic search
    
    When a message is added:
    1. Always add to Conversation Memory (short-term, recent)
    2. Optionally add to Vector Memory (long-term, searchable)
    """

    def __init__(self, memory_id: str):
        """
        Initialize memory manager.
        
        Args:
            memory_id: Unique ID for this agent/conversation
        """
        self.memory_id = memory_id
        self.conversation_memory = ConversationMemory(memory_id=memory_id)
        self.vector_memory = VectorMemory(memory_id=memory_id)

    async def add_message(
        self,
        role: str,
        content: str,
        save_to_vector: bool = True,
        metadata: Optional[dict] = None
    ) -> None:
        """
        Add message to memory.
        
        Args:
            role: "user" or "assistant"
            content: Message content
            save_to_vector: Also save to vector memory (long-term)
            metadata: Optional metadata
        """
        # Always save to short-term
        await self.conversation_memory.add_message(role, content, metadata)
        
        # Optionally save to long-term
        if save_to_vector:
            await self.vector_memory.add_message(role, content, metadata)

    async def get_recent_messages(self, limit: int = 10) -> List[MemoryMessage]:
        """
        Get recent messages for LLM context.
        
        Args:
            limit: Number of recent messages
            
        Returns:
            List of MemoryMessage objects
        """
        return await self.conversation_memory.get_messages(limit=limit)

    async def get_context_for_llm(self, max_tokens: int = 2000) -> str:
        """
        Get conversation history formatted for LLM context.
        
        Args:
            max_tokens: Max tokens to use for context
            
        Returns:
            Formatted string of conversation
        """
        return await self.conversation_memory.get_context_window(max_tokens)

    async def search_memory(
        self,
        query: str,
        use_vector: bool = True,
        limit: int = 10
    ) -> List[MemoryMessage]:
        """
        Search memory for relevant messages.
        
        Args:
            query: Search query
            use_vector: Use vector memory (semantic) vs conversation (recent)
            limit: Max results
            
        Returns:
            List of matching messages
        """
        if use_vector:
            return await self.vector_memory.search(query, limit=limit)
        else:
            return await self.conversation_memory.search(query, limit=limit)

    async def get_memory_summary(self) -> dict:
        """Get summary of all memory."""
        conv_summary = await self.conversation_memory.get_summary()
        vector_summary = await self.vector_memory.get_summary()
        vector_stats = await self.vector_memory.get_statistics()
        
        return {
            "conversation_summary": conv_summary,
            "vector_summary": vector_summary,
            "vector_statistics": vector_stats,
            "memory_id": self.memory_id
        }

    async def clear_conversation(self) -> None:
        """Clear conversation memory only (keep long-term)."""
        await self.conversation_memory.clear()

    async def clear_all(self) -> None:
        """Clear all memory."""
        await self.conversation_memory.clear()
        await self.vector_memory.clear()

    async def prepare_for_new_session(self) -> None:
        """
        Prepare memory for new session.
        
        Keeps vector memory but clears conversation memory.
        """
        await self.conversation_memory.clear()

    def get_info(self) -> dict:
        """Get memory manager information."""
        return {
            "memory_id": self.memory_id,
            "conversation_memory": self.conversation_memory.get_info(),
            "vector_memory": self.vector_memory.get_info()
        }
