"""Vector Memory - long-term memory with semantic search capability."""
import json
from typing import Optional, List, Dict, Any
from datetime import datetime
import redis.asyncio as redis
from app.memory.base_memory import BaseMemory, MemoryMessage
from app.core.config import settings


class VectorMemory(BaseMemory):
    """
    Long-term memory with semantic search capability.
    
    This is designed to eventually support vector databases like:
    - Pinecone
    - Weaviate
    - Milvus
    - FAISS
    
    For now, stores embeddings and metadata in Redis for later processing.
    """

    def __init__(
        self,
        memory_id: str,
        max_size: int = 1000,
        redis_client: Optional[redis.Redis] = None,
        embedding_model: Optional[str] = None
    ):
        """
        Initialize vector memory.
        
        Args:
            memory_id: Unique ID for this memory
            max_size: Max messages to store
            redis_client: Redis client
            embedding_model: Name of embedding model (e.g., "text-embedding-3-small")
        """
        super().__init__(memory_id=memory_id, max_size=max_size)
        self.redis_client = redis_client
        self.embedding_model = embedding_model or "text-embedding-3-small"
        self.messages_key = f"memory:vector:{memory_id}:messages"
        self.embeddings_key = f"memory:vector:{memory_id}:embeddings"
        self.metadata_key = f"memory:vector:{memory_id}:metadata"

    async def _get_redis(self) -> redis.Redis:
        """Get or create Redis client."""
        if not self.redis_client:
            self.redis_client = await redis.from_url(
                settings.REDIS_URL,
                decode_responses=True
            )
        return self.redis_client

    async def _get_embedding(self, text: str) -> Optional[List[float]]:
        """
        Get embedding for text.
        
        Currently returns None (placeholder).
        Future: Call OpenAI embedding API or local model.
        
        Args:
            text: Text to embed
            
        Returns:
            List of floats representing embedding
        """
        # TODO: Implement actual embedding
        # For now, just return None
        # Later: await openai.Embedding.create(model=self.embedding_model, input=text)
        return None

    async def add_message(
        self,
        role: str,
        content: str,
        metadata: Optional[dict] = None,
        embedding: Optional[List[float]] = None
    ) -> None:
        """
        Add message to vector memory.
        
        Args:
            role: "user" or "assistant"
            content: Message content
            metadata: Optional metadata
            embedding: Pre-computed embedding (optional)
        """
        redis_client = await self._get_redis()
        
        message = MemoryMessage(
            role=role,
            content=content,
            timestamp=datetime.now(),
            metadata=metadata
        )
        
        message_id = f"{self.memory_id}:{int(datetime.now().timestamp() * 1000)}"
        
        # Store message
        message_json = json.dumps(message.model_dump(mode='json'))
        await redis_client.hset(
            self.messages_key,
            message_id,
            message_json
        )
        
        # Get or compute embedding
        if embedding is None:
            embedding = await self._get_embedding(content)
        
        # Store embedding if available
        if embedding:
            embedding_json = json.dumps({"message_id": message_id, "embedding": embedding})
            await redis_client.hset(
                self.embeddings_key,
                message_id,
                embedding_json
            )
        
        # Store metadata
        metadata_to_store = {
            "message_id": message_id,
            "role": role,
            "timestamp": message.timestamp.isoformat(),
            "has_embedding": embedding is not None
        }
        if metadata:
            metadata_to_store.update(metadata)
        
        metadata_json = json.dumps(metadata_to_store)
        await redis_client.hset(
            self.metadata_key,
            message_id,
            metadata_json
        )
        
        # Set expiry (30 days)
        await redis_client.expire(self.messages_key, 30 * 24 * 60 * 60)
        await redis_client.expire(self.embeddings_key, 30 * 24 * 60 * 60)
        await redis_client.expire(self.metadata_key, 30 * 24 * 60 * 60)

    async def get_messages(self, limit: int = None) -> List[MemoryMessage]:
        """Get messages from vector memory."""
        redis_client = await self._get_redis()
        
        messages_dict = await redis_client.hgetall(self.messages_key)
        
        messages = []
        for msg_json in messages_dict.values():
            msg_dict = json.loads(msg_json)
            msg_dict['timestamp'] = datetime.fromisoformat(msg_dict['timestamp'])
            messages.append(MemoryMessage(**msg_dict))
        
        # Sort by timestamp
        messages.sort(key=lambda m: m.timestamp)
        
        # Limit if requested
        if limit:
            messages = messages[-limit:]
        
        return messages

    async def search(self, query: str, limit: int = 10) -> List[MemoryMessage]:
        """
        Search vector memory using semantic similarity.
        
        Currently uses simple text matching.
        Future: Use vector similarity search with embeddings.
        
        Args:
            query: Search query
            limit: Max results
            
        Returns:
            List of matching messages
        """
        messages = await self.get_messages()
        
        # Simple substring search (TODO: use embeddings for semantic search)
        results = [
            msg for msg in messages
            if query.lower() in msg.content.lower()
        ]
        
        return results[-limit:] if results else []

    async def clear(self) -> None:
        """Clear vector memory."""
        redis_client = await self._get_redis()
        await redis_client.delete(self.messages_key)
        await redis_client.delete(self.embeddings_key)
        await redis_client.delete(self.metadata_key)

    async def get_summary(self) -> str:
        """Get summary of vector memory."""
        messages = await self.get_messages()
        
        if not messages:
            return "No long-term memory stored."
        
        summary = f"Vector Memory Summary ({len(messages)} messages):\n"
        for i, msg in enumerate(messages[-5:], 1):  # Last 5
            preview = msg.content[:80]
            if len(msg.content) > 80:
                preview += "..."
            summary += f"{i}. [{msg.role}] {preview}\n"
        
        return summary

    async def get_statistics(self) -> Dict[str, Any]:
        """Get statistics about vector memory."""
        redis_client = await self._get_redis()
        
        message_count = await redis_client.hlen(self.messages_key)
        embedding_count = await redis_client.hlen(self.embeddings_key)
        
        messages = await self.get_messages()
        if messages:
            time_span = (messages[-1].timestamp - messages[0].timestamp).total_seconds()
        else:
            time_span = 0
        
        return {
            "total_messages": message_count,
            "messages_with_embeddings": embedding_count,
            "time_span_seconds": time_span,
            "embedding_model": self.embedding_model
        }

    async def export_for_vector_db(self) -> List[Dict[str, Any]]:
        """
        Export memory in format suitable for vector database ingestion.
        
        This prepares data to be moved to Pinecone, Weaviate, etc.
        
        Returns:
            List of dicts with message_id, content, embedding, metadata
        """
        redis_client = await self._get_redis()
        
        messages_dict = await redis_client.hgetall(self.messages_key)
        embeddings_dict = await redis_client.hgetall(self.embeddings_key)
        metadata_dict = await redis_client.hgetall(self.metadata_key)
        
        export_data = []
        
        for message_id, message_json in messages_dict.items():
            message_data = json.loads(message_json)
            
            # Get embedding if available
            embedding = None
            if message_id in embeddings_dict:
                embedding_data = json.loads(embeddings_dict[message_id])
                embedding = embedding_data.get("embedding")
            
            # Get metadata
            metadata = {}
            if message_id in metadata_dict:
                metadata = json.loads(metadata_dict[message_id])
            
            export_data.append({
                "message_id": message_id,
                "content": message_data.get("content"),
                "role": message_data.get("role"),
                "timestamp": message_data.get("timestamp"),
                "embedding": embedding,
                "metadata": metadata
            })
        
        return export_data
