from wissensdb.auth import AgentIdentity
from wissensdb.enums import AgentRole, KnowledgeStatus, KnowledgeType
from wissensdb.schemas import KnowledgeSource, KnowledgeWrite, Scope
from wissensdb.services import choose_status


def write_payload(kind: KnowledgeType, confidence: float = 0.8) -> KnowledgeWrite:
    return KnowledgeWrite(
        scope=Scope(project="example-project", repo="example-repo", area="backend"),
        type=kind,
        title="Memory module",
        content="Memory handling lives in the backend service.",
        confidence=confidence,
        source=KnowledgeSource(source_type="code_inspection", source_ref="src/memory.py"),
    )


def test_contributor_can_write_source_backed_code_map_as_active():
    agent = AgentIdentity(token="t", agent_id="codex", role=AgentRole.CONTRIBUTOR)

    assert choose_status(write_payload(KnowledgeType.CODE_MAP), agent) == KnowledgeStatus.ACTIVE


def test_contributor_architecture_write_needs_review():
    agent = AgentIdentity(token="t", agent_id="codex", role=AgentRole.CONTRIBUTOR)

    assert (
        choose_status(write_payload(KnowledgeType.ARCHITECTURE), agent)
        == KnowledgeStatus.NEEDS_REVIEW
    )


def test_maintainer_architecture_write_can_be_active():
    agent = AgentIdentity(token="t", agent_id="matze", role=AgentRole.MAINTAINER)

    assert choose_status(write_payload(KnowledgeType.ARCHITECTURE), agent) == KnowledgeStatus.ACTIVE


def test_low_confidence_write_needs_review():
    agent = AgentIdentity(token="t", agent_id="codex", role=AgentRole.CONTRIBUTOR)

    assert (
        choose_status(write_payload(KnowledgeType.GOTCHA, confidence=0.2), agent)
        == KnowledgeStatus.NEEDS_REVIEW
    )
