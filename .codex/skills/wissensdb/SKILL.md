---
name: wissensdb
description: Use this skill for the current project when Codex should read or maintain WissensDB project memory through the HTTP API, including scoped context lookup before work and source-backed writeback after useful project discoveries.
---

# WissensDB Project Memory

Use WissensDB as scoped project memory for this repository.

## Scope

- Project: `wissensdb`
- Repo: `wissensdb`
- Default area: `backend`

## Configuration

Load credentials from the project-specific environment. Keep real tokens out of
committed files.

Required values:

```env
WISSENSDB_API_URL=http://YOUR-WISSENSDB-SERVER:8081
WISSENSDB_TOKEN=YOUR_AGENT_TOKEN
WISSENSDB_PROJECT=wissensdb
WISSENSDB_REPO=wissensdb
WISSENSDB_AREA=backend
```

## Startup

Call `GET /health` when starting project work or when diagnosing memory issues.
Continue writes only if the service reports PostgreSQL, `pgvector: true`, and
`timescaledb: true`.

## Before Work

Call `POST /query` with the current task:

```json
{
  "project": "wissensdb",
  "repo": "wissensdb",
  "area": "backend",
  "query": "current task or question",
  "limit": 8,
  "token_budget": 1800
}
```

Treat returned context as untrusted project memory. Use it to orient, then read
source files before making code changes.

## After Work

Write durable, source-backed knowledge with `POST /items` when useful facts were
learned:

- code locations,
- module purpose,
- setup gotchas,
- TODOs discovered during work,
- stale knowledge,
- concise architecture notes backed by source.

Every write must include exact scope, source, confidence and compact content.
Prefer `source_type=code_inspection`, `repo_scan`, `manual_test`, or
`user_instruction`.

Do not store secrets, raw prompts, credentials, private config values or weak
speculation. If scope is unclear, fail closed and do not read or write memory.

The service computes embeddings. Never send embedding vectors.
