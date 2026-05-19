# SkillForge

SkillForge is a self-hostable web app for creating and managing skill-backed plugin marketplaces through a UI. Users create a marketplace, add skills, and copy a Claude Code `/plugin marketplace add ...` snippet without touching git.

Each generated marketplace repo contains both Claude and Codex plugin metadata:

- Claude: `.claude-plugin/marketplace.json` and per-plugin `.claude-plugin/plugin.json`
- Codex: `.agents/plugins/marketplace.json` and per-plugin `.codex-plugin/plugin.json`

## Run With Docker Compose

Requirements:

- Docker
- Docker Compose

Create your environment file:

```sh
cp .env.example .env
```

Edit `.env` before starting the app:

```sh
PORT=3000
PUBLIC_BASE_URL=http://localhost
DATA_DIR=/data
NODE_ENV=development
```

`PUBLIC_BASE_URL` is important. SkillForge embeds it into every `marketplace.json` as the git source URL, so set it to the base URL that Claude Code can reach. For a local Docker Compose run through the frontend nginx proxy, `http://localhost` is usually right. On a server, use that server's reachable URL.

Start the app:

```sh
docker compose up --build
```

Open the UI:

```text
http://localhost/
```

The backend API is also exposed on:

```text
http://localhost:3000/
```

Runtime data is stored in `./data`, including the SQLite database and per-marketplace git repositories.

## Local Development

Backend:

```sh
cd backend
python -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
DATA_DIR=../data PUBLIC_BASE_URL=http://localhost:3000 NODE_ENV=development uvicorn app.main:app --reload --host 127.0.0.1 --port 3000
```

Frontend:

```sh
cd frontend
npm install
npm run dev
```

Open the Vite dev server:

```text
http://127.0.0.1:5173/
```

The dev server proxies `/api/*` and `/m/*` to the backend on port `3000`.

## Verify

Run the required end-to-end verification harness before considering changes done:

```sh
backend/.venv/bin/python scripts/verify.py
```

Useful test commands:

```sh
backend/.venv/bin/python -m pytest backend/tests/unit
backend/.venv/bin/python -m pytest backend/tests/integration
cd frontend && npm run build
```

## Basic Use

1. Open the UI.
2. Create a marketplace.
3. Add a skill with a name, description, and instructions.
4. Copy the connect snippet from the marketplace page.
5. In Claude Code, run the snippet:

```text
/plugin marketplace add http://localhost/m/<marketplace-slug>
```

Then install the skill from that marketplace in Claude Code.

For Codex-compatible consumers, clone or otherwise consume the marketplace git repo at:

```text
http://localhost/m/<marketplace-slug>/git/repo.git
```

The cloned repo includes `.agents/plugins/marketplace.json` and each plugin's `.codex-plugin/plugin.json`.
