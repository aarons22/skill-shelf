# Development

## Backend

```sh
cd backend
python -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
SKILLSHELF_DATA_DIR=../.skillshelf-data PUBLIC_BASE_URL=http://localhost:3000 NODE_ENV=development uvicorn app.main:app --reload --host 127.0.0.1 --port 3000
```

## Frontend

```sh
cd frontend
npm install
npm run dev
```

Open the Vite dev server at:

```text
http://127.0.0.1:5173/
```

The dev server proxies `/api/*`, `/auth/*`, and `/m/*` to the backend on port `3000`.

## Docker Hot Reload

`docker compose up` automatically merges `docker-compose.override.yml`, which enables hot reload for both services:

```sh
cp .env.example .env
docker compose up --build
```

Open at `http://127.0.0.1/`. The override runs `uvicorn --reload` for backend changes and Vite HMR for frontend changes. Source files are bind-mounted into the containers; `node_modules` is preserved in a named volume so it is not clobbered by the mount.

For a production build (nginx-served static assets, no mounts), exclude the override explicitly:

```sh
docker compose -f docker-compose.yml up --build
```

## Verification

Run these before considering changes done:

```sh
backend/.venv/bin/python -m pytest backend/tests/unit
backend/.venv/bin/python -m pytest backend/tests/integration
cd frontend && npm run build
backend/.venv/bin/python scripts/verify.py
```

`scripts/verify.py` starts FastAPI on a random port with a temporary `SKILLSHELF_DATA_DIR`, creates marketplaces and plugins, clones generated git repos with dulwich, and verifies the Claude and Codex file layouts.

## Commit Discipline

Keep commits atomic and use imperative messages, for example `Add deployment docs` or `Remove top-level skill shortcuts`.
