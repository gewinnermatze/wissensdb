from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.http.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
)

from wissensdb.config import Settings
from wissensdb.vector_store import VectorHit


class QdrantVectorStore:
    def __init__(self, settings: Settings) -> None:
        self.collection = settings.qdrant_collection
        self.client = QdrantClient(url=settings.qdrant_url)
        self.dimension = settings.embedding_dimension
        self._ensure_collection()

    def _ensure_collection(self) -> None:
        collections = self.client.get_collections().collections
        if any(collection.name == self.collection for collection in collections):
            return
        self.client.create_collection(
            collection_name=self.collection,
            vectors_config=VectorParams(size=self.dimension, distance=Distance.COSINE),
        )

    def upsert(self, item_id: int, vector: list[float], payload: dict[str, Any]) -> None:
        self.client.upsert(
            collection_name=self.collection,
            points=[PointStruct(id=item_id, vector=vector, payload=payload)],
        )

    def search(
        self,
        vector: list[float],
        scope_filter: dict[str, Any],
        limit: int,
        include_needs_review: bool = False,
    ) -> list[VectorHit]:
        conditions = [
            FieldCondition(key=key, match=MatchValue(value=value))
            for key, value in scope_filter.items()
            if value is not None
        ]
        if not include_needs_review:
            conditions.append(FieldCondition(key="status", match=MatchValue(value="active")))

        response = self.client.search(
            collection_name=self.collection,
            query_vector=vector,
            query_filter=Filter(must=conditions),
            limit=limit,
        )
        return [VectorHit(item_id=int(hit.id), score=float(hit.score)) for hit in response]

    def delete(self, item_id: int) -> None:
        self.client.delete(collection_name=self.collection, points_selector=[item_id])


class LazyQdrantVectorStore:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._store: QdrantVectorStore | None = None

    @property
    def store(self) -> QdrantVectorStore:
        if self._store is None:
            self._store = QdrantVectorStore(self.settings)
        return self._store

    def upsert(self, item_id: int, vector: list[float], payload: dict[str, Any]) -> None:
        self.store.upsert(item_id, vector, payload)

    def search(
        self,
        vector: list[float],
        scope_filter: dict[str, Any],
        limit: int,
        include_needs_review: bool = False,
    ) -> list[VectorHit]:
        return self.store.search(vector, scope_filter, limit, include_needs_review)

    def delete(self, item_id: int) -> None:
        self.store.delete(item_id)
