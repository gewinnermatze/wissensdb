from fastapi import Depends, FastAPI, HTTPException, status
from sqlalchemy import text

from wissensdb.app_factory import build_service
from wissensdb.auth import (
    AgentIdentity,
    authenticate_project_token,
    current_token,
    projects_for_token,
)
from wissensdb.config import Settings, get_settings
from wissensdb.database import database_url_for_project, session_for_project, sessionmaker_for_url
from wissensdb.enums import AgentRole
from wissensdb.project_config import (
    ProjectConfigError,
    load_projects_config,
    project_routing_enabled,
)
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
def health(settings: Settings = Depends(get_settings)):
    if project_routing_enabled(settings):
        try:
            config = load_projects_config(settings)
        except ProjectConfigError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"invalid projects config: {exc}",
            ) from exc
        return {
            "status": "ok",
            "env": settings.env,
            "project_routing": True,
            "projects": len(config.projects),
            "embedding_provider": settings.embedding_provider,
            "embedding_dimension": settings.embedding_dimension,
        }

    session_factory = sessionmaker_for_url(database_url_for_project("", settings))
    with session_factory() as session:
        dialect = session.bind.dialect.name if session.bind else "unknown"
        extensions: set[str] = set()
        if dialect == "postgresql":
            extension_rows = session.execute(
                text(
                    """
                    SELECT extname
                    FROM pg_extension
                    WHERE extname IN ('vector', 'timescaledb')
                    """
                )
            ).scalars()
            extensions = set(extension_rows)
        else:
            session.execute(text("SELECT 1"))

        return {
            "status": "ok",
            "env": settings.env,
            "project_routing": False,
            "database": dialect,
            "pgvector": "vector" in extensions,
            "timescaledb": "timescaledb" in extensions,
            "embedding_provider": settings.embedding_provider,
            "embedding_dimension": settings.embedding_dimension,
        }


@app.post("/projects")
def create_project(
    payload: ProjectCreate,
    token: str = Depends(current_token),
    settings: Settings = Depends(get_settings),
):
    agent = project_agent(token, payload.slug, settings)
    require_http_role(agent, AgentRole.MAINTAINER)
    with session_for_project(payload.slug, settings) as session:
        service = build_service(session, settings)
        try:
            project = service.create_project(payload.slug, payload.name, payload.description)
        except GuardrailError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
        return {"id": project.id, "slug": project.slug, "name": project.name}


@app.post("/repos")
def create_repo(
    payload: RepoCreate,
    token: str = Depends(current_token),
    settings: Settings = Depends(get_settings),
):
    agent = project_agent(token, payload.project, settings)
    require_http_role(agent, AgentRole.MAINTAINER)
    with session_for_project(payload.project, settings) as session:
        service = build_service(session, settings)
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
    token: str = Depends(current_token),
    settings: Settings = Depends(get_settings),
):
    agent = project_agent(token, payload.project, settings)
    with session_for_project(payload.project, settings) as session:
        service = build_service(session, settings)
        try:
            return service.query(payload, agent)
        except (PermissionError, ScopeError) as exc:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


@app.post("/items", response_model=KnowledgeOut)
def upsert_item(
    payload: KnowledgeWrite,
    token: str = Depends(current_token),
    settings: Settings = Depends(get_settings),
):
    agent = project_agent(token, payload.scope.project, settings)
    with session_for_project(payload.scope.project, settings) as session:
        service = build_service(session, settings)
        try:
            return service.write(payload, agent)
        except PermissionError as exc:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
        except (GuardrailError, ScopeError, KeyError) as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@app.post("/projects/{project}/items/{item_id}/mark-stale", response_model=KnowledgeOut)
def mark_stale_for_project(
    project: str,
    item_id: int,
    token: str = Depends(current_token),
    settings: Settings = Depends(get_settings),
):
    agent = project_agent(token, project, settings)
    with session_for_project(project, settings) as session:
        return mark_stale_with_session(item_id, build_service(session, settings), agent)


@app.post("/projects/{project}/items/{item_id}/archive", response_model=KnowledgeOut)
def archive_for_project(
    project: str,
    item_id: int,
    token: str = Depends(current_token),
    settings: Settings = Depends(get_settings),
):
    agent = project_agent(token, project, settings)
    with session_for_project(project, settings) as session:
        return archive_with_session(item_id, build_service(session, settings), agent)


@app.post("/items/{item_id}/mark-stale", response_model=KnowledgeOut)
def mark_stale(
    item_id: int,
    token: str = Depends(current_token),
    settings: Settings = Depends(get_settings),
):
    project = single_project_for_token(token, settings)
    agent = project_agent(token, project, settings)
    with session_for_project(project, settings) as session:
        return mark_stale_with_session(item_id, build_service(session, settings), agent)


def mark_stale_with_session(item_id: int, service, agent: AgentIdentity) -> KnowledgeOut:
    try:
        return service.mark_stale(item_id, agent)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@app.post("/items/{item_id}/archive", response_model=KnowledgeOut)
def archive(
    item_id: int,
    token: str = Depends(current_token),
    settings: Settings = Depends(get_settings),
):
    project = single_project_for_token(token, settings)
    agent = project_agent(token, project, settings)
    with session_for_project(project, settings) as session:
        return archive_with_session(item_id, build_service(session, settings), agent)


def archive_with_session(item_id: int, service, agent: AgentIdentity) -> KnowledgeOut:
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


def project_agent(token: str, project: str, settings: Settings) -> AgentIdentity:
    try:
        return authenticate_project_token(token, project, settings)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


def single_project_for_token(token: str, settings: Settings) -> str:
    if not project_routing_enabled(settings):
        return ""
    projects = projects_for_token(token, settings)
    if not projects:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="invalid agent token")
    if len(projects) > 1:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="ambiguous project")
    return projects[0]
