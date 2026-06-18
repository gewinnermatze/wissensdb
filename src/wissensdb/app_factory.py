from functools import lru_cache

from sqlalchemy.orm import Session

from wissensdb.config import Settings, get_settings
from wissensdb.embeddings import build_embedding_provider
from wissensdb.qdrant_store import LazyQdrantVectorStore
from wissensdb.repositories import KnowledgeRepository
from wissensdb.services import KnowledgeService


@lru_cache
def get_vector_store():
    settings = get_settings()
    return LazyQdrantVectorStore(settings)


@lru_cache
def get_embedding_provider():
    settings = get_settings()
    return build_embedding_provider(settings)


def build_service(session: Session, settings: Settings | None = None) -> KnowledgeService:
    resolved_settings = settings or get_settings()
    return KnowledgeService(
        repository=KnowledgeRepository(session),
        embeddings=build_embedding_provider(resolved_settings)
        if settings
        else get_embedding_provider(),
        vector_store=LazyQdrantVectorStore(resolved_settings) if settings else get_vector_store(),
    )
