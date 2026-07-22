"""
Base repository with common CRUD operations.
"""

from typing import TypeVar, Generic, Optional, List, Dict, Any
from pydantic import BaseModel
from app.database.mongodb import mongodb

T = TypeVar('T', bound=BaseModel)


class BaseRepository(Generic[T]):
    """Base repository with common CRUD operations."""

    def __init__(self, collection_name: str, model_class: type):
        self.collection_name = collection_name
        self.model_class = model_class

    @property
    def collection(self):
        return mongodb.db[self.collection_name]

    async def create(self, data: T) -> bool:
        """Insert a new document."""
        try:
            doc = data.model_dump(mode="json")
            result = await self.collection.insert_one(doc)
            return bool(result.inserted_id)
        except Exception as e:
            raise

    async def update(self, filter_query: Dict[str, Any], data: Dict[str, Any]) -> bool:
        """Update documents matching the filter."""
        try:
            result = await self.collection.update_one(filter_query, {"$set": data})
            return result.modified_count > 0
        except Exception as e:
            raise

    async def find_one(self, filter_query: Dict[str, Any]) -> Optional[T]:
        """Find a single document."""
        try:
            doc = await self.collection.find_one(filter_query)
            if doc:
                return self.model_class(**doc)
            return None
        except Exception as e:
            raise

    async def find_many(self, filter_query: Dict[str, Any], limit: int = 100) -> List[T]:
        """Find multiple documents."""
        try:
            cursor = self.collection.find(filter_query).limit(limit)
            docs = await cursor.to_list(length=limit)
            return [self.model_class(**doc) for doc in docs]
        except Exception as e:
            raise

    async def delete(self, filter_query: Dict[str, Any]) -> bool:
        """Delete documents matching the filter."""
        try:
            result = await self.collection.delete_one(filter_query)
            return result.deleted_count > 0
        except Exception as e:
            raise