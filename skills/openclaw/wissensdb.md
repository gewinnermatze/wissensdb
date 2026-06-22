# WissensDB OpenClaw Tooling

OpenClaw agents should use the WissensDB HTTP API as their shared project memory.

WissensDB is backed by PostgreSQL with pgvector and TimescaleDB. OpenClaw agents
must not connect to PostgreSQL directly; all reads, writes, status changes and
embedding updates go through the HTTP API.

## Environment

- `WISSENSDB_API_URL`
- `WISSENSDB_TOKEN`
- `WISSENSDB_PROJECT`
- `WISSENSDB_REPO`
- optional `WISSENSDB_AREA`

## Startup Check

Call `GET /health` after deployment or when diagnosing memory issues. The
service should report PostgreSQL with `pgvector` and `timescaledb` enabled. If
health fails, skip memory writes and report the service problem.

## Tools

### `knowledge_search`

HTTP:

```http
POST /query
Authorization: Bearer ${WISSENSDB_TOKEN}
Content-Type: application/json
```

Body:

```json
{
  "project": "project-slug",
  "repo": "repo-slug",
  "area": "optional-area",
  "query": "task or question",
  "limit": 8,
  "token_budget": 1800
}
```

Use before answering project-specific implementation questions.

### `knowledge_upsert`

HTTP:

```http
POST /items
Authorization: Bearer ${WISSENSDB_TOKEN}
Content-Type: application/json
```

Use after work to persist durable knowledge. Always include source and confidence.
Do not send embedding vectors. The WissensDB service computes and stores
pgvector embeddings internally.

### `knowledge_mark_stale`

HTTP:

```http
POST /items/{item_id}/mark-stale
Authorization: Bearer ${WISSENSDB_TOKEN}
```

Use when code inspection proves an existing entry is outdated.

## Guardrails

- Never write without exact project and repo.
- Never write secrets, raw prompts or credentials.
- Prefer small, source-backed facts over broad summaries.
- Treat `needs_review` as uncertain.
- Use `source_type=user_instruction` when the user directly tells the agent to remember something.
- Use `source_type=code_inspection` or `repo_scan` for source-backed code facts.
