import os
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote_plus

import yaml
from dotenv import load_dotenv

from wissensdb.config import Settings, get_settings
from wissensdb.enums import AgentRole

ENV_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


@dataclass(frozen=True)
class ProjectToken:
    token: str
    agent_id: str
    role: AgentRole


@dataclass(frozen=True)
class ProjectRoute:
    slug: str
    database_url: str
    tokens: dict[str, ProjectToken]


@dataclass(frozen=True)
class ProjectsConfig:
    projects: dict[str, ProjectRoute]

    def route(self, project: str) -> ProjectRoute:
        try:
            return self.projects[project]
        except KeyError as exc:
            raise ProjectConfigError(f"unknown project in projects config: {project}") from exc

    def projects_for_token(self, token: str) -> list[ProjectRoute]:
        return [route for route in self.projects.values() if token in route.tokens]


class ProjectConfigError(ValueError):
    pass


def project_routing_enabled(settings: Settings | None = None) -> bool:
    resolved = settings or get_settings()
    return bool(resolved.projects_config)


def load_projects_config(settings: Settings | None = None) -> ProjectsConfig:
    resolved = settings or get_settings()
    if not resolved.projects_config:
        raise ProjectConfigError("WISSENSDB_PROJECTS_CONFIG is not set")
    load_dotenv(override=False)
    return load_projects_config_file(Path(resolved.projects_config))


@lru_cache
def load_projects_config_file(path: Path) -> ProjectsConfig:
    raw = yaml.safe_load(path.read_text()) or {}
    if not isinstance(raw, dict) or not isinstance(raw.get("projects"), dict):
        raise ProjectConfigError("projects config must contain a projects mapping")

    projects: dict[str, ProjectRoute] = {}
    for slug, project_raw in raw["projects"].items():
        if not isinstance(slug, str) or not slug.strip():
            raise ProjectConfigError("project slugs must be non-empty strings")
        if not isinstance(project_raw, dict):
            raise ProjectConfigError(f"project {slug} must be a mapping")
        database_url = _project_database_url(slug, project_raw)
        tokens = _project_tokens(slug, project_raw)
        projects[slug] = ProjectRoute(slug=slug, database_url=database_url, tokens=tokens)
    return ProjectsConfig(projects=projects)


def _project_database_url(slug: str, project_raw: dict) -> str:
    postgres = project_raw.get("postgres")
    if not isinstance(postgres, dict):
        raise ProjectConfigError(f"project {slug} requires postgres settings")
    host = _required_string(postgres, "host", slug)
    port = int(postgres.get("port", 5432))
    database = quote_plus(_required_string(postgres, "database", slug))
    user = quote_plus(_required_string(postgres, "user", slug))
    password = quote_plus(_required_string(postgres, "password", slug))
    return f"postgresql+psycopg://{user}:{password}@{host}:{port}/{database}"


def _project_tokens(slug: str, project_raw: dict) -> dict[str, ProjectToken]:
    token_groups = project_raw.get("tokens")
    if not isinstance(token_groups, dict):
        raise ProjectConfigError(f"project {slug} requires tokens")

    tokens: dict[str, ProjectToken] = {}
    for role_name, role_tokens in token_groups.items():
        try:
            role = AgentRole(role_name)
        except ValueError as exc:
            raise ProjectConfigError(f"invalid role for project {slug}: {role_name}") from exc
        if not isinstance(role_tokens, dict):
            raise ProjectConfigError(f"tokens for role {role_name} in {slug} must be a mapping")
        for agent_id, raw_token in role_tokens.items():
            if not isinstance(agent_id, str) or not agent_id.strip():
                raise ProjectConfigError(f"token agent id in project {slug} must be non-empty")
            token = substitute_env(raw_token)
            if not token:
                raise ProjectConfigError(f"empty token for {slug}/{role_name}/{agent_id}")
            if token in tokens:
                raise ProjectConfigError(f"duplicate token in project {slug}")
            tokens[token] = ProjectToken(token=token, agent_id=agent_id, role=role)
    return tokens


def _required_string(mapping: dict, key: str, project_slug: str) -> str:
    value = substitute_env(mapping.get(key))
    if not value:
        raise ProjectConfigError(f"project {project_slug} requires postgres.{key}")
    return value


def substitute_env(value) -> str:
    if not isinstance(value, str):
        return "" if value is None else str(value)

    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in os.environ:
            raise ProjectConfigError(f"missing environment variable: {name}")
        return os.environ[name]

    return ENV_PATTERN.sub(replace, value)
