# WissensDB

WissensDB is a small Python/FastAPI service for scoped project knowledge that coding agents can read and maintain automatically. MariaDB stores structured knowledge, versions, roles and audit events. Qdrant stores vector embeddings for token-cheap semantic retrieval.

## Architecture

- `FastAPI` exposes the LAN API for agents.
- `Typer` provides the `wissensdb` CLI for setup, migrations, scans and admin tasks.
- `MariaDB` stores projects, repos, areas, knowledge items, versions and audit events.
- `Qdrant` stores embeddings with scope payloads.
- Agent access is via Bearer tokens, not direct DB access.

Every read and write is scoped by `project + repo + optional area`. Ambiguous scope fails closed.

## Quick Start

```bash
cp .env.example .env
python -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head
wissensdb project create example-project "Example Project"
wissensdb repo add example-project example-repo /srv/repos/example-repo --area backend
uvicorn wissensdb.main:app --host 0.0.0.0 --port 8080
```

Agents can then call:

```bash
curl -H "Authorization: Bearer agent-token-contributor" \
  -H "Content-Type: application/json" \
  http://knowledge-server.local:8080/query \
  -d '{"project":"example-project","repo":"example-repo","query":"where is memory handled?"}'
```

## Automatic Agent Writes

Agents may write automatically when:

- the scope is explicit,
- their token role allows it,
- a source is present,
- the entry has a confidence score,
- the write is not a high-risk knowledge type.

High-risk types such as `goal`, `decision` and `architecture` become `needs_review` unless written by a maintainer. All writes create versions and audit events.

## Deployment

Docker Compose is the recommended server deployment. A systemd+venv unit is also included in `deploy/wissensdb.service`.

```bash
docker compose up -d --build
```

The compose file expects MariaDB and Qdrant to be reachable from the service container. Adjust `.env` hostnames to your server network.

## Agent Skills

- Codex skill: `skills/codex/SKILL.md`
- OpenClaw skill/tool notes: `skills/openclaw/wissensdb.md`

Both skills require agents to query scoped context before work and store new project knowledge after relevant work.
