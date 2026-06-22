from pathlib import Path

import typer
from sqlalchemy.orm import Session

from wissensdb.app_factory import build_service
from wissensdb.auth import AgentIdentity
from wissensdb.database import SessionLocal
from wissensdb.enums import AgentRole
from wissensdb.scanner import scan_repo
from wissensdb.schemas import Scope

app = typer.Typer(help="WissensDB admin and ingestion CLI.")
project_app = typer.Typer(help="Manage projects.")
repo_app = typer.Typer(help="Manage repositories.")
scan_app = typer.Typer(help="Scan repositories.")
reindex_app = typer.Typer(help="Recompute knowledge item embeddings.")
app.add_typer(project_app, name="project")
app.add_typer(repo_app, name="repo")
app.add_typer(scan_app, name="scan")
app.add_typer(reindex_app, name="reindex")


def maintainer_identity() -> AgentIdentity:
    return AgentIdentity(token="cli", agent_id="cli", role=AgentRole.MAINTAINER)


def contributor_identity() -> AgentIdentity:
    return AgentIdentity(token="cli", agent_id="cli-scan", role=AgentRole.CONTRIBUTOR)


@project_app.command("create")
def create_project(slug: str, name: str, description: str | None = None):
    with SessionLocal() as session:
        service = build_service(session)
        project = service.create_project(slug, name, description)
        typer.echo(f"created project {project.slug} ({project.id})")


@repo_app.command("add")
def add_repo(
    project: str,
    slug: str,
    path: Path,
    name: str | None = None,
    area: str | None = typer.Option(None, "--area"),
):
    with SessionLocal() as session:
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
    with SessionLocal() as session:
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
    with SessionLocal() as session:
        service = build_service(session)
        count = service.reindex_scope(
            Scope(project=project, repo=repo, area=area),
            maintainer_identity(),
            include_inactive=include_inactive,
        )
        typer.echo(f"reindexed {count} items")


@app.command("serve")
def serve(host: str = "0.0.0.0", port: int = 8080):
    import uvicorn

    uvicorn.run("wissensdb.main:app", host=host, port=port)
