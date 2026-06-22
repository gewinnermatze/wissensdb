from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON
from sqlalchemy.engine import Dialect
from sqlalchemy.types import TypeDecorator

DEFAULT_EMBEDDING_DIMENSION = 768


class EmbeddingVector(TypeDecorator):
    """Use pgvector on PostgreSQL and JSON elsewhere for fast unit tests."""

    impl = JSON
    cache_ok = False

    def __init__(self, dimension: int = DEFAULT_EMBEDDING_DIMENSION, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.dimension = dimension

    def load_dialect_impl(self, dialect: Dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(Vector(self.dimension))
        return dialect.type_descriptor(JSON())
