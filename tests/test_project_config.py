import pytest

from wissensdb.enums import AgentRole
from wissensdb.project_config import ProjectConfigError, load_projects_config_file


def write_config(tmp_path, content: str):
    path = tmp_path / "projects.yaml"
    path.write_text(content)
    return path


def test_loads_project_config_with_env_substitution(tmp_path, monkeypatch):
    monkeypatch.setenv("PROJECT_DB_PASSWORD", "secret")
    monkeypatch.setenv("PROJECT_CODEX_TOKEN", "codex-token")
    path = write_config(
        tmp_path,
        """
projects:
  sample:
    postgres:
      host: postgres
      port: 5432
      database: sample_db
      user: sample_user
      password: ${PROJECT_DB_PASSWORD}
    tokens:
      maintainer:
        codex: ${PROJECT_CODEX_TOKEN}
""",
    )

    config = load_projects_config_file(path)
    route = config.route("sample")

    assert route.database_url == "postgresql+psycopg://sample_user:secret@postgres:5432/sample_db"
    assert route.tokens["codex-token"].agent_id == "codex"
    assert route.tokens["codex-token"].role == AgentRole.MAINTAINER


def test_rejects_invalid_roles(tmp_path, monkeypatch):
    monkeypatch.setenv("PROJECT_DB_PASSWORD", "secret")
    path = write_config(
        tmp_path,
        """
projects:
  sample:
    postgres:
      host: postgres
      database: sample_db
      user: sample_user
      password: ${PROJECT_DB_PASSWORD}
    tokens:
      typo-role:
        codex: token
""",
    )

    with pytest.raises(ProjectConfigError, match="invalid role"):
        load_projects_config_file(path)


def test_missing_env_var_fails_closed(tmp_path):
    path = write_config(
        tmp_path,
        """
projects:
  sample:
    postgres:
      host: postgres
      database: sample_db
      user: sample_user
      password: ${MISSING_DB_PASSWORD}
    tokens:
      maintainer:
        codex: token
""",
    )

    with pytest.raises(ProjectConfigError, match="missing environment variable"):
        load_projects_config_file(path)
