from pathlib import Path

import typer
from alembic import command
from alembic.config import Config as AlembicConfig
from sqlalchemy.orm import Session

from wissensdb.app_factory import build_service
from wissensdb.auth import AgentIdentity
from wissensdb.config import get_settings
from wissensdb.database import SessionLocal, database_url_for_project, session_for_project
from wissensdb.enums import AgentRole
from wissensdb.project_config import load_projects_config, project_routing_enabled
from wissensdb.scanner import scan_repo
from wissensdb.schemas import Scope

app = typer.Typer(help="WissensDB admin and ingestion CLI.")
project_app = typer.Typer(help="Manage projects.")
projects_app = typer.Typer(help="Validate multi-project configuration.")
repo_app = typer.Typer(help="Manage repositories.")
scan_app = typer.Typer(help="Scan repositories.")
reindex_app = typer.Typer(help="Recompute knowledge item embeddings.")
app.add_typer(project_app, name="project")
app.add_typer(projects_app, name="projects")
app.add_typer(repo_app, name="repo")
app.add_typer(scan_app, name="scan")
app.add_typer(reindex_app, name="reindex")


def maintainer_identity() -> AgentIdentity:
    return AgentIdentity(token="cli", agent_id="cli", role=AgentRole.MAINTAINER)


def contributor_identity() -> AgentIdentity:
    return AgentIdentity(token="cli", agent_id="cli-scan", role=AgentRole.CONTRIBUTOR)


@project_app.command("create")
def create_project(slug: str, name: str, description: str | None = None):
    settings = get_settings()
    session_context = (
        session_for_project(slug, settings) if project_routing_enabled(settings) else SessionLocal()
    )
    with session_context as session:
        service = build_service(session)
        project = service.create_project(slug, name, description)
        typer.echo(f"created project {project.slug} ({project.id})")


@project_app.command("migrate")
def migrate_project(
    project: str | None = typer.Argument(None),
    all_projects: bool = typer.Option(False, "--all"),
):
    settings = get_settings()
    if all_projects:
        if not project_routing_enabled(settings):
            raise typer.BadParameter("--all requires WISSENSDB_PROJECTS_CONFIG")
        config = load_projects_config(settings)
        for slug, route in config.projects.items():
            _run_migrations(route.database_url)
            typer.echo(f"migrated project {slug}")
        return
    if not project:
        raise typer.BadParameter("project is required unless --all is used")
    _run_migrations(database_url_for_project(project, settings))
    typer.echo(f"migrated project {project}")


@projects_app.command("validate-config")
def validate_projects_config():
    config = load_projects_config(get_settings())
    typer.echo(f"valid projects config: {len(config.projects)} projects")


@repo_app.command("add")
def add_repo(
    project: str,
    slug: str,
    path: Path,
    name: str | None = None,
    area: str | None = typer.Option(None, "--area"),
):
    settings = get_settings()
    session_context = (
        session_for_project(project, settings)
        if project_routing_enabled(settings)
        else SessionLocal()
    )
    with session_context as session:
        service = build_service(session)
        repo = service.create_repo(project, slug, name or slug, str(path.resolve()), area)
        typer.echo(f"created repo {repo.slug} ({repo.id})")


@scan_app.command("repo")
def scan_repository(
    project: str,
    repo: str,
    path: Path,
    area: str | None = typer.Option(None, "--area"),
    max_files: int = typer.Option(300, "--max-files"),
):
    settings = get_settings()
    session_context = (
        session_for_project(project, settings)
        if project_routing_enabled(settings)
        else SessionLocal()
    )
    with session_context as session:
        _scan(session, project, repo, path, area, max_files)


def _scan(
    session: Session,
    project: str,
    repo: str,
    path: Path,
    area: str | None,
    max_files: int,
) -> None:
    service = build_service(session)
    writes = scan_repo(path, Scope(project=project, repo=repo, area=area), max_files=max_files)
    agent = contributor_identity()
    count = 0
    for write in writes:
        service.write(write, agent)
        count += 1
    typer.echo(f"scanned {count} files")


@reindex_app.command("repo")
def reindex_repository(
    project: str,
    repo: str,
    area: str | None = typer.Option(None, "--area"),
    include_inactive: bool = typer.Option(False, "--include-inactive"),
):
    settings = get_settings()
    session_context = (
        session_for_project(project, settings)
        if project_routing_enabled(settings)
        else SessionLocal()
    )
    with session_context as session:
        service = build_service(session)
        count = service.reindex_scope(
            Scope(project=project, repo=repo, area=area),
            maintainer_identity(),
            include_inactive=include_inactive,
        )
        typer.echo(f"reindexed {count} items")


def _run_migrations(database_url: str) -> None:
    alembic_config = AlembicConfig("alembic.ini")
    alembic_config.attributes["database_url"] = database_url
    command.upgrade(alembic_config, "head")


@app.command("serve")
def serve(host: str = "0.0.0.0", port: int = 8080):
    import uvicorn

    uvicorn.run("wissensdb.main:app", host=host, port=port)
