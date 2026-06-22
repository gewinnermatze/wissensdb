# WissensDB

WissensDB is a small Python/FastAPI service for scoped project knowledge that coding agents can read and maintain automatically. PostgreSQL stores structured knowledge, vector embeddings, versions, roles, audit events and agent event streams.

## Architecture

- `FastAPI` exposes the LAN API for agents.
- `Typer` provides the `wissensdb` CLI for setup, migrations, scans and admin tasks.
- `PostgreSQL` stores projects, repos, areas, knowledge items, versions and roles.
- `pgvector` stores embeddings on `knowledge_items` for scoped semantic retrieval.
- `TimescaleDB` stores time-series audit, ingestion and agent events as hypertables.
- Agent access is via Bearer tokens, not direct DB access.

Every read and write is scoped by `project + repo + optional area`. Ambiguous scope fails closed.

## Quick Start

```bash
cp .env.example .env
docker compose --profile db up -d postgres
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

Docker Compose is the recommended API deployment. A systemd+venv unit is also included in `deploy/wissensdb.service`.

### Install From Public Image

The API image is published to GitHub Container Registry:

```text
ghcr.io/gewinnermatze/wissensdb:latest
```

On the server:

```bash
mkdir -p /opt/wissensdb
cd /opt/wissensdb
curl -fsSLO https://raw.githubusercontent.com/gewinnermatze/wissensdb/main/docker-compose.prod.yml
curl -fsSLO https://raw.githubusercontent.com/gewinnermatze/wissensdb/main/.env.example
cp .env.example .env
```

Set your PostgreSQL container name or LAN host in `.env`:

```env
WISSENSDB_POSTGRES_HOST=postgres
WISSENSDB_POSTGRES_PORT=5432
WISSENSDB_POSTGRES_DB=wissensdb
WISSENSDB_POSTGRES_USER=wissensdb
WISSENSDB_POSTGRES_PASSWORD=change-me
```

`WISSENSDB_POSTGRES_HOST` is the value that must match the PostgreSQL container
name when both containers share a Docker network. You can still set
`WISSENSDB_DATABASE_URL` directly if you need a fully custom connection string;
when present it overrides the individual PostgreSQL settings.

Then start the API:

```bash
docker compose -f docker-compose.prod.yml up -d
```

By default the container runs `alembic upgrade head` before starting the API. Set
`WISSENSDB_RUN_MIGRATIONS=false` if migrations are managed separately.

Check the service:

```bash
curl http://localhost:8080/health
```

The response should report `pgvector: true` and `timescaledb: true`.

### Embeddings

The default embedding provider is `hash`, which is local and useful for setup
and smoke tests. For better semantic search, use one of the model-backed
providers.

OpenAI:

```env
WISSENSDB_EMBEDDING_PROVIDER=openai
WISSENSDB_EMBEDDING_DIMENSION=1536
OPENAI_API_KEY=...
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
```

Ollama on the local network:

```env
WISSENSDB_EMBEDDING_PROVIDER=ollama
WISSENSDB_EMBEDDING_DIMENSION=768
WISSENSDB_OLLAMA_URL=http://ollama:11434
WISSENSDB_OLLAMA_EMBEDDING_MODEL=nomic-embed-text-v2-moe
```

`WISSENSDB_EMBEDDING_DIMENSION` must match the selected embedding model before
the database migration creates `knowledge_items.embedding`. For
`nomic-embed-text-v2-moe`, keep PostgreSQL/pgvector at `vector(768)`.

### Local Build Or Bundled Database

The API expects PostgreSQL with both `vector` and `timescaledb` extensions. Use an existing LAN PostgreSQL server by setting `WISSENSDB_POSTGRES_HOST` and the matching database credentials, or start the bundled database profile for local/server testing:

```bash
docker compose --profile db up -d postgres
docker compose up -d --build wissensdb-api
```

The bundled `postgres` service uses a TimescaleDB PostgreSQL image and the migration enables both required extensions. If your PostgreSQL image does not include `pgvector`, `alembic upgrade head` fails clearly.

### Publishing The Image

Images are built and pushed by `.github/workflows/container.yml` on every push to
`main`, plus version tags such as `v0.1.0`. The workflow publishes:

- `ghcr.io/gewinnermatze/wissensdb:latest`
- `ghcr.io/gewinnermatze/wissensdb:sha-<commit>`
- `ghcr.io/gewinnermatze/wissensdb:<tag>` for release tags

If GitHub creates the package as private on the first run, set the package
visibility to public once in the GitHub Container Registry package settings.

## Agent Skills

- Codex skill: `skills/codex/SKILL.md`
- OpenClaw skill/tool notes: `skills/openclaw/wissensdb.md`

Both skills require agents to query scoped context before work and store new project knowledge after relevant work.
