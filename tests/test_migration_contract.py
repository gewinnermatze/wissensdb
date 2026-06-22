from pathlib import Path

MIGRATION = Path("migrations/versions/0001_initial.py")


def test_initial_migration_enables_postgres_extensions():
    text = MIGRATION.read_text(encoding="utf-8")

    assert "CREATE EXTENSION IF NOT EXISTS vector" in text
    assert "CREATE EXTENSION IF NOT EXISTS timescaledb" in text


def test_initial_migration_uses_pgvector_and_hypertables():
    text = MIGRATION.read_text(encoding="utf-8")

    assert '"embedding", Vector(embedding_dimension())' in text
    assert "USING hnsw (embedding vector_cosine_ops)" in text
    assert "create_hypertable('audit_events', 'created_at'" in text
    assert "create_hypertable('ingestion_runs', 'started_at'" in text
    assert "create_hypertable('agent_events', 'created_at'" in text
