from enum import StrEnum


class AgentRole(StrEnum):
    READER = "reader"
    CONTRIBUTOR = "contributor"
    MAINTAINER = "maintainer"


class KnowledgeStatus(StrEnum):
    ACTIVE = "active"
    NEEDS_REVIEW = "needs_review"
    STALE = "stale"
    ARCHIVED = "archived"


class KnowledgeType(StrEnum):
    CODE_MAP = "code_map"
    ARCHITECTURE = "architecture"
    GOAL = "goal"
    TODO = "todo"
    DECISION = "decision"
    SETUP = "setup"
    GOTCHA = "gotcha"
    NOTE = "note"


HIGH_RISK_TYPES = {
    KnowledgeType.ARCHITECTURE,
    KnowledgeType.GOAL,
    KnowledgeType.DECISION,
}


ROLE_RANK = {
    AgentRole.READER: 0,
    AgentRole.CONTRIBUTOR: 1,
    AgentRole.MAINTAINER: 2,
}
