from fastapi import Depends, FastAPI, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from wissensdb.app_factory import build_service
from wissensdb.auth import AgentIdentity, current_agent
from wissensdb.config import Settings, get_settings
from wissensdb.database import get_session
from wissensdb.enums import AgentRole
from wissensdb.repositories import ScopeError
from wissensdb.schemas import (
    KnowledgeOut,
    KnowledgeWrite,
    ProjectCreate,
    QueryRequest,
    QueryResponse,
    RepoCreate,
)
from wissensdb.services import GuardrailError

app = FastAPI(title="WissensDB", version="0.1.0")


@app.get("/health")
def health(session: Session = Depends(get_session), settings: Settings = Depends(get_settings)):
    session.execute(text("SELECT 1"))
    return {
        "status": "ok",
        "env": settings.env,
        "qdrant_collection": settings.qdrant_collection,
        "embedding_provider": settings.embedding_provider,
    }


@app.post("/projects")
def create_project(
    payload: ProjectCreate,
    session: Session = Depends(get_session),
    agent: AgentIdentity = Depends(current_agent),
):
    require_http_role(agent, AgentRole.MAINTAINER)
    service = build_service(session)
    try:
        project = service.create_project(payload.slug, payload.name, payload.description)
    except GuardrailError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return {"id": project.id, "slug": project.slug, "name": project.name}


@app.post("/repos")
def create_repo(
    payload: RepoCreate,
    session: Session = Depends(get_session),
    agent: AgentIdentity = Depends(current_agent),
):
    require_http_role(agent, AgentRole.MAINTAINER)
    service = build_service(session)
    try:
        repo = service.create_repo(
            payload.project,
            payload.slug,
            payload.name,
            payload.path,
            payload.default_area,
        )
    except (GuardrailError, ScopeError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return {"id": repo.id, "slug": repo.slug, "name": repo.name}


@app.post("/query", response_model=QueryResponse)
def query(
    payload: QueryRequest,
    session: Session = Depends(get_session),
    agent: AgentIdentity = Depends(current_agent),
):
    service = build_service(session)
    try:
        return service.query(payload, agent)
    except (PermissionError, ScopeError) as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


@app.post("/items", response_model=KnowledgeOut)
def upsert_item(
    payload: KnowledgeWrite,
    session: Session = Depends(get_session),
    agent: AgentIdentity = Depends(current_agent),
):
    service = build_service(session)
    try:
        return service.write(payload, agent)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except (GuardrailError, ScopeError, KeyError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@app.post("/items/{item_id}/mark-stale", response_model=KnowledgeOut)
def mark_stale(
    item_id: int,
    session: Session = Depends(get_session),
    agent: AgentIdentity = Depends(current_agent),
):
    service = build_service(session)
    try:
        return service.mark_stale(item_id, agent)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@app.post("/items/{item_id}/archive", response_model=KnowledgeOut)
def archive(
    item_id: int,
    session: Session = Depends(get_session),
    agent: AgentIdentity = Depends(current_agent),
):
    service = build_service(session)
    try:
        return service.archive(item_id, agent)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


def require_http_role(agent: AgentIdentity, role: AgentRole) -> None:
    try:
        agent.require(role)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
