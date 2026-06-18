import pytest

from wissensdb.auth import authenticate_token, parse_agent_tokens
from wissensdb.config import Settings
from wissensdb.enums import AgentRole


def test_parse_agent_tokens():
    identities = parse_agent_tokens("abc:coding-agent:contributor,def:reader-agent:reader")

    assert identities["abc"].agent_id == "coding-agent"
    assert identities["abc"].role == AgentRole.CONTRIBUTOR
    assert identities["def"].role == AgentRole.READER


def test_authenticate_token_rejects_unknown_token():
    settings = Settings(agent_tokens="abc:coding-agent:contributor")

    with pytest.raises(PermissionError):
        authenticate_token("missing", settings)
