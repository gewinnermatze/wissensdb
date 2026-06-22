# WissensDB Codex Skill

Use this skill whenever working inside a project that is registered in WissensDB.

WissensDB is backed by PostgreSQL with pgvector and TimescaleDB. Agents must use the
HTTP API only; do not connect directly to PostgreSQL, inspect database tables, or
write embeddings yourself.

## Required Configuration

- `WISSENSDB_API_URL`: base URL, for example `http://knowledge-server.local:8080`
- `WISSENSDB_TOKEN`: bearer token for this Codex agent
- `WISSENSDB_PROJECT`: project slug
- `WISSENSDB_REPO`: repo slug
- `WISSENSDB_AREA`: optional area

## Startup Check

If the API was just deployed or changed, call `GET /health` first. A healthy
production service should report PostgreSQL plus enabled `pgvector` and
`timescaledb`. If the health check is unavailable or extensions are missing,
do not attempt project-memory writes.

## Before Project Work

1. Query WissensDB with the concrete task:
   - `POST /query`
   - include `project`, `repo`, optional `area`, `query`, `limit`, `token_budget`
2. Treat returned context as project memory, not as a replacement for reading files.
3. Prefer entries with source paths, commit SHAs and higher confidence.
4. Do not use `needs_review` entries as settled truth unless the user explicitly asks for uncertain context.

## After Relevant Work

Automatically write back useful durable knowledge:

- where important code lives,
- what a module/service does,
- setup gotchas,
- TODOs discovered during implementation,
- stale knowledge detected from code changes,
- concise architectural observations backed by source.

Use `POST /items` with:

- exact project/repo/area scope,
- `source_type`,
- `source_ref`,
- file path and commit when available,
- confidence score,
- short title and compact content.

The service computes and stores the pgvector embedding. The agent should send
semantic content, not embedding vectors.

Do not store secrets, raw prompts, private tool config, credentials, or speculation without clear source. If scope is unclear, do not write.

## Status Expectations

The service decides whether writes become `active` or `needs_review`. High-risk types such as `goal`, `decision` and `architecture` may be held for review unless this agent has maintainer rights.
