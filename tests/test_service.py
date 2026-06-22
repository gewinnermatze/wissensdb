import json

import pytest
from pgvector import Vector
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from wissensdb.auth import AgentIdentity
from wissensdb.database import Base
from wissensdb.embeddings import HashEmbeddingProvider
from wissensdb.enums import AgentRole, KnowledgeStatus, KnowledgeType
from wissensdb.models import KnowledgeItem
from wissensdb.repositories import KnowledgeRepository, ScopeError, item_to_snapshot, json_safe
from wissensdb.schemas import KnowledgeSource, KnowledgeWrite, QueryRequest, Scope
from wissensdb.services import KnowledgeService


def build_test_service():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    service = KnowledgeService(
        KnowledgeRepository(session),
        HashEmbeddingProvider(64),
    )
    return service, session


def test_write_creates_audit_and_query_returns_scoped_context():
    service, session = build_test_service()
    service.create_project("example-project", "Example Project")
    service.create_repo("example-project", "example-repo", "Example Repo")
    agent = AgentIdentity(token="t", agent_id="coding-agent", role=AgentRole.CONTRIBUTOR)

    created = service.write(
        KnowledgeWrite(
            scope=Scope(project="example-project", repo="example-repo", area="backend"),
            type=KnowledgeType.CODE_MAP,
            title="Memory repository",
            content="The memory repository persists scoped memories.",
            confidence=0.9,
            source=KnowledgeSource(
                source_type="code_inspection",
                source_ref="src/memory.py",
                path="src/memory.py",
                commit_sha="abc123",
            ),
        ),
        agent,
    )

    assert created.status == KnowledgeStatus.ACTIVE
    stored = session.get(KnowledgeItem, created.id)
    assert stored is not None
    assert stored.embedding

    result = service.query(
        QueryRequest(
            project="example-project",
            repo="example-repo",
            area="backend",
            query="memory repository",
        ),
        agent,
    )

    assert result.hits
    assert "Memory repository" in result.context
    assert session.execute(text("select count(*) from audit_events")).scalar_one() >= 2


def test_unknown_scope_fails_closed():
    service, _session = build_test_service()
    service.create_project("example-project", "Example Project")
    agent = AgentIdentity(token="t", agent_id="coding-agent", role=AgentRole.CONTRIBUTOR)

    try:
        service.query(
            QueryRequest(project="example-project", repo="missing", query="anything"),
            agent,
        )
    except ScopeError:
        pass
    else:
        raise AssertionError("unknown repo should fail closed")


def test_update_existing_item_creates_json_safe_version():
    service, session = build_test_service()
    service.create_project("example-project", "Example Project")
    service.create_repo("example-project", "example-repo", "Example Repo")
    agent = AgentIdentity(token="t", agent_id="coding-agent", role=AgentRole.CONTRIBUTOR)

    created = service.write(
        KnowledgeWrite(
            scope=Scope(project="example-project", repo="example-repo", area="backend"),
            type=KnowledgeType.SETUP,
            title="Initial setup",
            content="Initial setup note.",
            confidence=0.8,
            source=KnowledgeSource(source_type="manual_test", source_ref="test"),
        ),
        agent,
    )

    updated = service.write(
        KnowledgeWrite(
            item_id=created.id,
            scope=Scope(project="example-project", repo="example-repo", area="backend"),
            type=KnowledgeType.SETUP,
            title="Updated setup",
            content="Updated setup note.",
            confidence=0.9,
            source=KnowledgeSource(source_type="manual_test", source_ref="test-update"),
        ),
        agent,
    )

    assert updated.version == 2
    snapshot = session.execute(text("select snapshot from knowledge_versions")).scalar_one()
    if isinstance(snapshot, str):
        snapshot = json.loads(snapshot)
    json.dumps(snapshot)
    assert snapshot["title"] == "Initial setup"
    assert snapshot["version"] == 1


def test_mark_stale_returns_original_scope_slugs_and_creates_version():
    service, session = build_test_service()
    service.create_project("example-project", "Example Project")
    service.create_repo("example-project", "example-repo", "Example Repo")
    agent = AgentIdentity(token="t", agent_id="coding-agent", role=AgentRole.CONTRIBUTOR)

    created = service.write(
        KnowledgeWrite(
            scope=Scope(project="example-project", repo="example-repo", area="backend"),
            type=KnowledgeType.GOTCHA,
            title="Old gotcha",
            content="Old gotcha content.",
            confidence=0.8,
            source=KnowledgeSource(source_type="manual_test", source_ref="test"),
        ),
        agent,
    )

    stale = service.mark_stale(created.id, agent)

    assert stale.status == KnowledgeStatus.STALE
    assert stale.scope.project == "example-project"
    assert stale.scope.repo == "example-repo"
    assert stale.version == 2
    assert session.execute(text("select count(*) from knowledge_versions")).scalar_one() == 1


def test_snapshot_with_pgvector_embedding_is_json_safe():
    item = KnowledgeItem(
        id=1,
        project_id=1,
        repo_id=1,
        area="backend",
        type=KnowledgeType.CODE_MAP,
        status=KnowledgeStatus.ACTIVE,
        title="Vector item",
        content="Content",
        confidence=0.9,
        source_type="manual_test",
        source_ref="test",
        embedding=Vector([0.1, 0.2, 0.3]),
        created_by="agent",
        updated_by="agent",
        version=1,
    )

    snapshot = json_safe(item_to_snapshot(item))

    assert snapshot["embedding"] == pytest.approx([0.1, 0.2, 0.3])
    json.dumps(snapshot)
