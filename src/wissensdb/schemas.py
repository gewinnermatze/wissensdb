from pydantic import BaseModel, Field, field_validator

from wissensdb.enums import AgentRole, KnowledgeStatus, KnowledgeType


class Scope(BaseModel):
    project: str = Field(min_length=1)
    repo: str = Field(min_length=1)
    area: str | None = None

    @field_validator("project", "repo", "area")
    @classmethod
    def clean_slug(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            return None
        return cleaned


class ProjectCreate(BaseModel):
    slug: str
    name: str
    description: str | None = None


class RepoCreate(BaseModel):
    project: str
    slug: str
    name: str
    path: str | None = None
    default_area: str | None = None


class KnowledgeSource(BaseModel):
    source_type: str = Field(min_length=1, max_length=80)
    source_ref: str = Field(min_length=1, max_length=1024)
    path: str | None = None
    line_start: int | None = None
    line_end: int | None = None
    commit_sha: str | None = None
    content_hash: str | None = None


class KnowledgeWrite(BaseModel):
    scope: Scope
    type: KnowledgeType
    title: str = Field(min_length=1, max_length=255)
    content: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    source: KnowledgeSource
    item_id: int | None = None


class KnowledgeOut(BaseModel):
    id: int
    scope: Scope
    type: KnowledgeType
    status: KnowledgeStatus
    title: str
    content: str
    confidence: float
    source: KnowledgeSource
    created_by: str
    updated_by: str
    version: int


class QueryRequest(BaseModel):
    project: str
    repo: str
    area: str | None = None
    query: str = Field(min_length=1)
    limit: int = Field(default=8, ge=1, le=30)
    token_budget: int = Field(default=1800, ge=200, le=8000)
    include_needs_review: bool = False


class QueryHit(BaseModel):
    item: KnowledgeOut
    score: float | None = None


class QueryResponse(BaseModel):
    scope: Scope
    hits: list[QueryHit]
    context: str


class AgentCreate(BaseModel):
    id: str
    role: AgentRole
    display_name: str | None = None


class AuditOut(BaseModel):
    id: int
    action: str
    actor: str
    role: AgentRole
    item_id: int | None
    detail: dict | None
