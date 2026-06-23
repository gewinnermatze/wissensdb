from collections.abc import Generator
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from wissensdb.config import Settings, get_settings
from wissensdb.project_config import load_projects_config, project_routing_enabled


class Base(DeclarativeBase):
    pass


def build_engine(database_url: str | None = None):
    url = database_url or get_settings().resolved_database_url
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, pool_pre_ping=True, connect_args=connect_args)


@lru_cache
def sessionmaker_for_url(database_url: str):
    engine_for_url = build_engine(database_url)
    return sessionmaker(
        bind=engine_for_url,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )


def database_url_for_project(project: str, settings: Settings | None = None) -> str:
    resolved = settings or get_settings()
    if project_routing_enabled(resolved):
        return load_projects_config(resolved).route(project).database_url
    return resolved.resolved_database_url


@contextmanager
def session_for_project(project: str, settings: Settings | None = None):
    session_factory = sessionmaker_for_url(database_url_for_project(project, settings))
    with session_factory() as session:
        yield session


engine = build_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def get_session() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        yield session
