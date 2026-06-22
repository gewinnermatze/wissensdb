from sqlalchemy.orm import Session

from wissensdb.config import Settings, get_settings
from wissensdb.embeddings import build_embedding_provider
from wissensdb.repositories import KnowledgeRepository
from wissensdb.services import KnowledgeService


def build_service(session: Session, settings: Settings | None = None) -> KnowledgeService:
    resolved_settings = settings or get_settings()
    return KnowledgeService(
        repository=KnowledgeRepository(session),
        embeddings=build_embedding_provider(resolved_settings),
    )
