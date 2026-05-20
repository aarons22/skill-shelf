# Deployment

## Docker Compose

Copy the example environment and set the public URL before starting:

```sh
cp .env.example .env
docker compose up --build
```

Important settings:

```sh
PUBLIC_BASE_URL=https://your-server.example.com
SKILLSHELF_DATA_DIR=/var/lib/skillshelf
NODE_ENV=production
```

The Compose file sets `SKILLSHELF_DATA_DIR=/var/lib/skillshelf` for the backend container even if your local `.env` uses a development path.

`PUBLIC_BASE_URL` must be reachable by Claude Code and Codex clients. SkillShelf embeds it into every Claude marketplace entry as the git source URL.

## Persistent Storage

SkillShelf stores both SQLite metadata and generated per-marketplace git repos under `SKILLSHELF_DATA_DIR`. These must stay together because SQLite is the source of truth for metadata and the git repos are the source of truth for distributed plugin files.

The default Compose file mounts a named volume at `/var/lib/skillshelf`:

```yaml
volumes:
  skillshelf-data:
```

For cloud deployments, attach durable storage to that path and include it in backups. A restore should bring back the entire directory, including:

- `skillshelf.db`
- `marketplaces/<slug>/repo`
- `marketplaces/<slug>/working`

## Reverse Proxy And TLS

Put the frontend behind HTTPS and proxy these paths to the backend through the frontend nginx service:

- `/api/*`
- `/m/*`

Git smart-HTTP uses streaming responses, so keep proxy buffering disabled for `/m/*` when using another reverse proxy.

## Health

The backend exposes:

```text
GET /health
```

The Compose file uses that endpoint for the backend healthcheck before starting the frontend.
