# SkillForge — Agent Reference

This is the living reference for every coding agent working on this repo. When this file contradicts the original spec, this file wins. Update it in the same commit as any code change that contradicts it.

---

## What the product is

**SkillForge** is a self-hostable web app that lets non-technical users create and manage plugin marketplaces for Claude Code through a UI. Each marketplace is a named, addressable endpoint a user adds to their AI coding agent. Inside each marketplace, the user uploads "skills" (prose instructions that customize agent behavior).

The user's experience:
1. `docker compose up` on a server they own.
2. Open the web UI. Create a marketplace — give it a name. The UI shows the URL to add to Claude Code.
3. Add skills through a form (name, description, content).
4. From Claude Code: `/plugin marketplace add https://their-server/m/<slug>`.
5. Skills appear in the agent and can be installed.

The user **never** sees, types, or learns git, even though git is the storage engine.

### Who this is for

Internal teams sharing **proprietary** business-process skills. Single-tenant, behind a company's network or VPN. We are not building a public marketplace.

### Non-goals for v1

- Authentication or user accounts
- LLM-assisted skill authoring
- MCP server / hook / agent / command authoring (skills only)
- Codex `.codex-plugin/plugin.json` emission
- Anthropic Cowork ZIP export
- Permissions, approval workflows, audit logs

---

## The multi-marketplace model

This is load-bearing.

A **marketplace** is the unit the user creates first and shares with collaborators. It maps 1:1 to what Claude Code calls a "plugin marketplace" — what you `/plugin marketplace add` to. A single SkillForge instance hosts many marketplaces side by side.

Each marketplace has:
- A slug (URL-safe id, e.g. `finance-team-skills`)
- A display name
- An owner name and email (used as the git author when committing)
- Its own git repo on disk
- Its own `marketplace.json` endpoint at `/m/<slug>` and `/m/<slug>/marketplace.json`
- Its own git smart-HTTP endpoint at `/m/<slug>/git/repo.git`
- A collection of skills, each rendered as a single-skill plugin inside the repo

A skill belongs to exactly one marketplace. Cross-marketplace sharing is post-v1.

### Canonical user flow

```
User opens app
  └─ Empty state: "Create your first marketplace"
       └─ User creates "Finance Team Skills"
            └─ Lands on marketplace page
                 ├─ Shows the "Connect" snippet with the actual URL to copy
                 ├─ Empty skills list with "Add skill" button
                 └─ Settings tab (rename, owner info, delete)
                      └─ User clicks "Add skill"
                           └─ Fills form, saves, returns to marketplace page
                                └─ Skill appears in list
```

Top-level navigation always shows the list of marketplaces. Skill management always happens inside a specific marketplace context.

---

## Tech stack

**This is not the original spec's stack.** The backend was switched to Python before any code was written (user preference).

| Layer | Choice | Rationale |
|---|---|---|
| Backend API | **Python 3.12 + FastAPI** | User has strong aversion to TS on the backend; FastAPI is idiomatic Python with built-in validation |
| Git layer | **dulwich** (pure Python) | No git binary required in the container — same constraint as the original spec; dulwich has both smart-HTTP server and client |
| Database | **SQLite via SQLAlchemy 2.x Core + Alembic** | No ORM — explicit SQL-shaped code; Alembic for migrations |
| Tests | **pytest** | Standard Python |
| Frontend | **React + Vite + Tailwind** | Unchanged from spec; no component library |
| Deployment | **Two services in docker-compose** | Backend (FastAPI/uvicorn) + Frontend (nginx serving Vite build); nginx reverse-proxies `/api/*` and `/m/*` to backend |

Deviate from this stack only with a stated concrete reason.

---

## Repo layout

```
skillforge/
├── AGENTS.md                   # This file — always up to date
├── CLAUDE.md                   # One line: @AGENTS.md
├── README.md
├── docker-compose.yml
├── .env.example
├── backend/
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── alembic.ini
│   ├── alembic/
│   ├── app/
│   │   ├── main.py             # FastAPI entrypoint, uvicorn target
│   │   ├── config.py           # env loading (PORT, PUBLIC_BASE_URL, DATA_DIR)
│   │   ├── db.py               # SQLAlchemy engine + session factory
│   │   ├── models.py           # Core Table objects (no ORM classes)
│   │   ├── schemas.py          # Pydantic request/response models
│   │   ├── routes/
│   │   │   ├── api_marketplaces.py
│   │   │   ├── api_skills.py
│   │   │   ├── marketplace_public.py   # /m/{slug} endpoints
│   │   │   └── git_smart_http.py       # /m/{slug}/git/repo.git/*
│   │   └── lib/
│   │       ├── git_store.py
│   │       ├── slug.py
│   │       ├── skill_validator.py
│   │       └── marketplace_json.py
│   └── tests/
│       ├── unit/
│       └── integration/
├── frontend/
│   ├── Dockerfile              # multi-stage: vite build → nginx
│   ├── nginx.conf
│   ├── package.json
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   ├── index.html
│   └── src/
│       ├── main.tsx
│       ├── App.tsx
│       ├── pages/
│       │   ├── MarketplacesList.tsx
│       │   ├── MarketplaceDetail.tsx
│       │   ├── NewMarketplace.tsx
│       │   └── SkillEditor.tsx
│       └── components/
├── data/                       # Runtime — mounted as volume
│   ├── marketplaces/
│   │   └── <slug>/
│   │       ├── repo/           # Bare git repo
│   │       └── working/        # Working tree
│   └── skillforge.db
└── scripts/
    └── verify.py               # The self-verification harness
```

---

## Data model

SQLite is the source of truth for metadata. The per-marketplace git repo is the source of truth for file content. The two are kept in sync **only** through `git_store.py`. Direct filesystem writes outside `git_store.py` are a bug.

### Schema

```sql
CREATE TABLE marketplaces (
  slug          TEXT PRIMARY KEY,
  display_name  TEXT NOT NULL,
  owner_name    TEXT NOT NULL,
  owner_email   TEXT NOT NULL,
  created_at    INTEGER NOT NULL,
  updated_at    INTEGER NOT NULL
);

CREATE TABLE skills (
  marketplace_slug  TEXT NOT NULL REFERENCES marketplaces(slug) ON DELETE CASCADE,
  slug              TEXT NOT NULL,
  display_name      TEXT NOT NULL,
  description       TEXT NOT NULL,
  version           TEXT NOT NULL DEFAULT '1.0.0',
  content           TEXT NOT NULL,
  created_at        INTEGER NOT NULL,
  updated_at        INTEGER NOT NULL,
  last_commit       TEXT,
  PRIMARY KEY (marketplace_slug, slug)
);
```

### On-disk layout inside a marketplace's git repo

```
<repo-working-root>/
├── .claude-plugin/
│   └── marketplace.json
└── plugins/
    └── <skill-slug>/
        ├── .claude-plugin/
        │   └── plugin.json
        └── skills/
            └── <skill-slug>/
                └── SKILL.md
```

`SKILL.md` format:

```markdown
---
name: <skill-slug>
description: <description>
---
<content>
```

Each skill is wrapped as a single-skill plugin because Claude Code's installable unit is the plugin, not the skill. This wrapping is invisible to the user.

---

## The marketplace.json contract

Served at `GET /m/<slug>` and `GET /m/<slug>/marketplace.json` (identical content, regenerated from DB on each request). Also committed to the repo at `.claude-plugin/marketplace.json` so the repo is consumable via `git clone`.

```json
{
  "name": "<slug>",
  "owner": { "name": "<owner_name>", "email": "<owner_email>" },
  "plugins": [
    {
      "name": "<skill-slug>",
      "description": "<description>",
      "version": "<version>",
      "source": {
        "source": "url",
        "url": "<PUBLIC_BASE_URL>/m/<slug>/git/repo.git",
        "path": "plugins/<skill-slug>"
      }
    }
  ]
}
```

**Use `source: "url"` + `path`**, not relative paths. Relative paths in a URL-distributed `marketplace.json` silently fail to resolve. This is documented Claude Code behavior.

---

## API surface

All under `/api`, JSON in / JSON out. No auth in v1.

### Marketplaces

| Method | Path | Notes |
|---|---|---|
| `GET` | `/api/marketplaces` | List all |
| `GET` | `/api/marketplaces/{slug}` | One + skill count |
| `POST` | `/api/marketplaces` | Body: `displayName, ownerName, ownerEmail`; server derives slug; 409 on collision |
| `PUT` | `/api/marketplaces/{slug}` | Partial update; cannot change slug |
| `DELETE` | `/api/marketplaces/{slug}` | Cascades to skills, removes on-disk repo |

### Skills (nested)

| Method | Path | Notes |
|---|---|---|
| `GET` | `/api/marketplaces/{slug}/skills` | Metadata only |
| `GET` | `/api/marketplaces/{slug}/skills/{skill_slug}` | Full content |
| `POST` | `/api/marketplaces/{slug}/skills` | Body: `displayName, description, content`; server derives skillSlug |
| `PUT` | `/api/marketplaces/{slug}/skills/{skill_slug}` | Partial; bumps patch version |
| `DELETE` | `/api/marketplaces/{slug}/skills/{skill_slug}` | |

### Non-`/api` routes

| Method | Path | Response |
|---|---|---|
| `GET` | `/m/{slug}` | `marketplace.json` (from DB) |
| `GET` | `/m/{slug}/marketplace.json` | Alias |
| `GET` | `/m/{slug}/git/repo.git/*` | Git smart-HTTP, read-only |

---

## The canonical write path

Every mutation follows this shape. No exceptions.

1. Validate input (Pydantic + manual checks).
2. Open SQLAlchemy `Connection.begin()` transaction.
3. INSERT / UPDATE / DELETE the SQLite row.
4. Write / remove files in `data/marketplaces/<slug>/working/`.
5. Regenerate `.claude-plugin/marketplace.json` in the working tree from current DB state — always full rewrite, never patch.
6. `git_store.commit(...)` — **single dulwich commit** containing both the skill files and the regenerated `marketplace.json`.
7. Update `last_commit` on affected skill rows.
8. `COMMIT` the SQLAlchemy transaction.

On any exception in steps 4–7: SQLAlchemy rolls back; explicitly reset the working tree from the bare repo via dulwich (file-system writes are not covered by the DB transaction rollback).

Atomicity is non-negotiable. A `git clone` between two commits should never see a `marketplace.json` that disagrees with the plugin folders.

---

## Self-verification loop

**Run `python scripts/verify.py` before declaring any task complete.** Don't ask the human. Don't move on if it fails. Fix it first.

### What `scripts/verify.py` does (all 12 steps must pass)

1. Start the FastAPI server on a random free port with a temporary `DATA_DIR`.
2. `POST /api/marketplaces` → create "Finance Team Skills".
3. `GET /m/finance-team-skills/marketplace.json` → assert valid JSON, empty `plugins`, correct `name`/`owner`.
4. `POST /api/marketplaces/finance-team-skills/skills` → create "Quarterly Report Process".
5. Re-fetch `marketplace.json` → assert skill appears with correct `source.url`, `source.path`, `description`.
6. `dulwich.porcelain.clone` from `http://localhost:<port>/m/finance-team-skills/git/repo.git` into a temp dir.
7. Assert cloned repo contains the expected files (§ on-disk layout) with correct content.
8. `PUT` an edit to the skill's content. Re-clone. Assert updated content.
9. `DELETE` the skill. Re-fetch `marketplace.json` → skill gone. Re-clone → plugin folder gone.
10. Create a second marketplace + skill. Assert it has its own `/m/<slug>` and git repo, fully isolated.
11. `DELETE` the first marketplace. Assert its endpoints return 404 and its on-disk repo is removed. Assert second marketplace is untouched.
12. Shut down server. Exit 0 on success, non-zero with diff/log on failure.

### When the loop breaks

If the human reports a bug the harness missed:
1. Add a failing test case to the harness that reproduces the bug.
2. Fix the bug.
3. Update this file to describe what the harness now covers.

All three changes go in the same commit.

### npm / pytest commands

- `pytest backend/tests/unit` — pure functions. Run on every save.
- `pytest backend/tests/integration` — API + DB. Run before committing.
- `python scripts/verify.py` — the gate. Must pass before any task is "done."

---

## Things easy to get wrong

- **`marketplace.json` byte-for-byte conformance.** Claude Code parses this strictly. Use `source: "url"` + `path`, never relative paths.
- **Slug derivation.** NFKD strip accents, lowercase, collapse non-alphanumerics to single dashes, trim leading/trailing dashes, cap at 64 chars. Test: `"Q4 — Sales Report 📊"` → `q4-sales-report`. On collision, return 409 — **do not auto-suffix**.
- **`source.path` uses forward slashes on all platforms.** Never `os.path.join` for this field. Use `posixpath.join` or template strings.
- **Skill files and `marketplace.json` go in the same dulwich commit.** Splitting them produces inconsistent clones.
- **No subprocess to git.** Container must not need a git binary. dulwich only.
- **`PUBLIC_BASE_URL` is the most important config.** If it's wrong, every `source.url` in every `marketplace.json` is unreachable. Log it on startup. Warn if it points at `localhost` outside dev mode.
- **Working-tree cleanup on failure.** File-system writes are not covered by the SQLAlchemy rollback. Must explicitly reset the working tree from the bare repo when steps 4–7 of the write path fail.

---

## Configuration

```
PORT=3000
PUBLIC_BASE_URL=http://localhost:3000   # CRITICAL — embedded in marketplace.json
DATA_DIR=./data
NODE_ENV=development
```

Loaded by `backend/app/config.py` using Pydantic `BaseSettings`. Log `PUBLIC_BASE_URL` on startup. Warn loudly if it contains `localhost` and `NODE_ENV != development`.

---

## Manual acceptance test

The verify harness covers everything except the actual Claude Code client. Before declaring v1 done, the human runs this checklist:

1. `docker compose up`.
2. Open the UI. Create a marketplace called "Hello Marketplace."
3. The marketplace detail page shows a `/plugin marketplace add ...` snippet.
4. Add a skill called "Hello World" with description "A test skill" and content "Say hello to the user when asked."
5. In Claude Code: run the snippet from step 3. Then `/plugin install hello-world@hello-marketplace`.
6. Start a new Claude Code session. Ask "say hello." The skill activates.
7. Edit the skill in the UI. Run `/plugin marketplace update` in Claude Code. The new content takes effect.
8. Delete the skill. Run `/plugin marketplace update`. The skill is gone.
9. Delete the marketplace. The endpoints return 404.

If any step fails, the verify harness missed something. Add a test for it.

---

## dulwich notes (from the spike — verified working)

- **Bare repo init**: `Repo.init_bare(path)` requires the target directory to **already exist** (`os.makedirs(path)` first).
- **Working tree**: same — `os.makedirs(work_path)` before `Repo.init(work_path)`.
- **Default branch**: dulwich defaults to `master`, not `main`. Use `refs/heads/master` in push refspecs.
- **Smart-HTTP server**: `DictBackend({"/": bare_repo})` + `make_wsgi_chain(backend)` from `dulwich.web`. The `"/"` key matches any incoming path prefix.
- **WSGI → ASGI bridge**: `starlette.middleware.wsgi.WSGIMiddleware` is **deprecated** and broken for git's streaming responses (chunked `IncompleteRead` errors). Use **`a2wsgi.WSGIMiddleware`** instead. Add `a2wsgi` to `pyproject.toml` dependencies.
- **Mounting**: `app.mount("/m/<slug>/git", WSGIMiddleware(dulwich_wsgi))` — a2wsgi correctly bridges the streaming git-pack protocol.
- **Commit pattern**: init working tree → write files → `porcelain.add` + `porcelain.commit` → `porcelain.push` to bare. The git store (`git_store.py`) uses dulwich's `Repo` object and `index` directly for committing to avoid the double-repo overhead in production (write to working tree, stage, `repo.do_commit`).
