# WissensDB Codex Skill

Use this skill whenever working inside a project that is registered in WissensDB.

## Required Configuration

- `WISSENSDB_API_URL`: base URL, for example `http://knowledge-server.local:8080`
- `WISSENSDB_TOKEN`: bearer token for this Codex agent
- `WISSENSDB_PROJECT`: project slug
- `WISSENSDB_REPO`: repo slug
- `WISSENSDB_AREA`: optional area

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

Do not store secrets, raw prompts, private tool config, credentials, or speculation without clear source. If scope is unclear, do not write.

## Status Expectations

The service decides whether writes become `active` or `needs_review`. High-risk types such as `goal`, `decision` and `architecture` may be held for review unless this agent has maintainer rights.
