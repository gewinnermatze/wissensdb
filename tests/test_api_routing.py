from contextlib import contextmanager

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from wissensdb.config import Settings, get_settings
from wissensdb.database import Base
from wissensdb.main import app
from wissensdb.models import KnowledgeItem


def create_project_db(project: str, repo: str):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    with session_factory() as session:
        from wissensdb.app_factory import build_service

        service = build_service(
            session,
            Settings(embedding_provider="hash", embedding_dimension=64),
        )
        service.create_project(project, project)
        service.create_repo(project, repo, repo)
    return session_factory


def write_config(tmp_path, monkeypatch, shared_token: bool = False):
    monkeypatch.setenv("A_PASSWORD", "a-secret")
    monkeypatch.setenv("B_PASSWORD", "b-secret")
    monkeypatch.setenv("A_TOKEN", "token-a")
    monkeypatch.setenv("B_TOKEN", "token-b")
    monkeypatch.setenv("B_SECOND_TOKEN", "token-b-second")
    tmp_path.mkdir(parents=True, exist_ok=True)
    path = tmp_path / "projects.yaml"
    second_b = "${A_TOKEN}" if shared_token else "${B_SECOND_TOKEN}"
    path.write_text(
        f"""
projects:
  project-a:
    postgres:
      host: postgres
      database: project_a
      user: user_a
      password: ${{A_PASSWORD}}
    tokens:
      maintainer:
        codex-a: ${{A_TOKEN}}
  project-b:
    postgres:
      host: postgres
      database: project_b
      user: user_b
      password: ${{B_PASSWORD}}
    tokens:
      maintainer:
        codex-b: ${{B_TOKEN}}
        second-b: {second_b}
""",
    )
    return path


def build_client(tmp_path, monkeypatch, shared_token: bool = False):
    config_path = write_config(tmp_path, monkeypatch, shared_token=shared_token)
    settings = Settings(
        projects_config=str(config_path),
        embedding_provider="hash",
        embedding_dimension=64,
    )
    sessions = {
        "project-a": create_project_db("project-a", "repo-a"),
        "project-b": create_project_db("project-b", "repo-b"),
    }

    @contextmanager
    def fake_session_for_project(project: str, _settings=None):
        with sessions[project]() as session:
            yield session

    app.dependency_overrides[get_settings] = lambda: settings
    monkeypatch.setattr("wissensdb.main.session_for_project", fake_session_for_project)
    return TestClient(app), sessions


def test_token_can_only_write_its_configured_project(tmp_path, monkeypatch):
    client, sessions = build_client(tmp_path, monkeypatch)
    payload = {
        "scope": {"project": "project-a", "repo": "repo-a", "area": "backend"},
        "type": "note",
        "title": "Project A only",
        "content": "This should land in project A only.",
        "confidence": 0.9,
        "source": {"source_type": "manual_test", "source_ref": "api-routing"},
    }

    response = client.post("/items", json=payload, headers={"Authorization": "Bearer token-a"})

    assert response.status_code == 200
    assert response.json()["created_by"] == "codex-a"
    with sessions["project-a"]() as session:
        assert session.query(KnowledgeItem).count() == 1
    with sessions["project-b"]() as session:
        assert session.query(KnowledgeItem).count() == 0

    forbidden = client.post(
        "/items",
        json={**payload, "scope": {"project": "project-b", "repo": "repo-b"}},
        headers={"Authorization": "Bearer token-a"},
    )
    assert forbidden.status_code == 403


def test_project_status_route_disambiguates_same_item_ids(tmp_path, monkeypatch):
    client, sessions = build_client(tmp_path, monkeypatch)
    for project, repo, token in [
        ("project-a", "repo-a", "token-a"),
        ("project-b", "repo-b", "token-b"),
    ]:
        response = client.post(
            "/items",
            json={
                "scope": {"project": project, "repo": repo},
                "type": "note",
                "title": f"{project} item",
                "content": "same local id in isolated databases",
                "confidence": 0.9,
                "source": {"source_type": "manual_test", "source_ref": "api-routing"},
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert response.json()["id"] == 1

    stale = client.post(
        "/projects/project-b/items/1/mark-stale",
        headers={"Authorization": "Bearer token-b"},
    )

    assert stale.status_code == 200
    assert stale.json()["scope"]["project"] == "project-b"
    assert stale.json()["status"] == "stale"
    with sessions["project-a"]() as session:
        assert session.get(KnowledgeItem, 1).status.value == "active"
    with sessions["project-b"]() as session:
        assert session.get(KnowledgeItem, 1).status.value == "stale"


def test_old_status_route_rejects_ambiguous_project(tmp_path, monkeypatch):
    client, _sessions = build_client(tmp_path, monkeypatch)
    ambiguous = client.post("/items/1/mark-stale", headers={"Authorization": "Bearer missing"})
    assert ambiguous.status_code == 403

    client, _sessions = build_client(tmp_path / "shared-token", monkeypatch, shared_token=True)
    response = client.post("/items/1/mark-stale", headers={"Authorization": "Bearer token-a"})
    assert response.status_code == 400
    assert response.json()["detail"] == "ambiguous project"
