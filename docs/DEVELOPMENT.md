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

The dev server proxies `/api/*` and `/m/*` to the backend on port `3000`.

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
