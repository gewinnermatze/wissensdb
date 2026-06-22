from wissensdb.config import Settings


def test_database_url_is_built_from_postgres_host_settings():
    settings = Settings(
        database_url=None,
        postgres_host="postgres",
        postgres_port=5432,
        postgres_db="project_db",
        postgres_user="project_user",
        postgres_password="secret",
    )

    assert (
        settings.resolved_database_url
        == "postgresql+psycopg://project_user:secret@postgres:5432/project_db"
    )


def test_database_url_override_wins():
    settings = Settings(database_url="postgresql+psycopg://custom")

    assert settings.resolved_database_url == "postgresql+psycopg://custom"
