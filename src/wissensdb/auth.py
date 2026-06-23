from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from wissensdb.config import Settings, get_settings
from wissensdb.enums import ROLE_RANK, AgentRole
from wissensdb.project_config import (
    ProjectConfigError,
    load_projects_config,
    project_routing_enabled,
)


@dataclass(frozen=True)
class AgentIdentity:
    token: str
    agent_id: str
    role: AgentRole
    project: str | None = None

    def require(self, role: AgentRole) -> None:
        if ROLE_RANK[self.role] < ROLE_RANK[role]:
            raise PermissionError(f"{self.role} cannot perform {role} action")


def parse_agent_tokens(raw_tokens: str) -> dict[str, AgentIdentity]:
    identities: dict[str, AgentIdentity] = {}
    if not raw_tokens.strip():
        return identities

    for part in raw_tokens.split(","):
        token_part = part.strip()
        if not token_part:
            continue
        try:
            token, agent_id, role = token_part.split(":", 2)
        except ValueError as exc:
            raise ValueError("WISSENSDB_AGENT_TOKENS entries must be token:agent_id:role") from exc
        identities[token] = AgentIdentity(token=token, agent_id=agent_id, role=AgentRole(role))
    return identities


def authenticate_token(token: str, settings: Settings) -> AgentIdentity:
    identity = parse_agent_tokens(settings.agent_tokens).get(token)
    if identity is None:
        raise PermissionError("invalid agent token")
    return identity


def authenticate_project_token(token: str, project: str, settings: Settings) -> AgentIdentity:
    if not project_routing_enabled(settings):
        return authenticate_token(token, settings)
    try:
        route = load_projects_config(settings).route(project)
    except ProjectConfigError as exc:
        raise PermissionError(str(exc)) from exc
    project_token = route.tokens.get(token)
    if project_token is None:
        raise PermissionError("invalid agent token for project")
    return AgentIdentity(
        token=token,
        agent_id=project_token.agent_id,
        role=project_token.role,
        project=project,
    )


def projects_for_token(token: str, settings: Settings) -> list[str]:
    if not project_routing_enabled(settings):
        identity = authenticate_token(token, settings)
        return [identity.project] if identity.project else [""]
    return [route.slug for route in load_projects_config(settings).projects_for_token(token)]


bearer_scheme = HTTPBearer(auto_error=False)


def current_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> str:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing bearer token",
        )
    return credentials.credentials


def current_agent(
    token: str = Depends(current_token),
    settings: Settings = Depends(get_settings),
) -> AgentIdentity:
    try:
        return authenticate_token(token, settings)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
