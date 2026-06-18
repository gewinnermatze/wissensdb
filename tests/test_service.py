from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from wissensdb.auth import AgentIdentity
from wissensdb.database import Base
from wissensdb.embeddings import HashEmbeddingProvider
from wissensdb.enums import AgentRole, KnowledgeStatus, KnowledgeType
from wissensdb.repositories import KnowledgeRepository, ScopeError
from wissensdb.schemas import KnowledgeSource, KnowledgeWrite, QueryRequest, Scope
from wissensdb.services import KnowledgeService
from wissensdb.vector_store import InMemoryVectorStore


def build_test_service():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    service = KnowledgeService(
        KnowledgeRepository(session),
        HashEmbeddingProvider(64),
        InMemoryVectorStore(),
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
