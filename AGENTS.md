# SkillShelf — Agent Reference

This is the living reference for every coding agent working on this repo. When this file contradicts the original spec, this file wins. Update it in the same commit as any code change that contradicts it.

---

## What the product is

**SkillShelf** is a self-hostable web app that lets non-technical users create and manage plugin marketplaces for Claude Code and Codex through a UI. Each marketplace is a named, addressable endpoint a user adds to their AI coding agent. Inside each marketplace, the user creates installable plugins with guided components: skills, hooks, agents, MCP servers, commands, monitors, and default settings.

The user's experience:
1. `docker compose up` on a server they own.
2. Open the web UI. On a fresh install, complete `/setup`; Local Accounts is the built-in offline identity provider and the first setup user becomes organization admin.
3. Create a marketplace — give it a name. The UI shows the URL to add to Claude Code.
4. Add plugins and guided components through forms. Skills are added inside a plugin.
5. From Claude Code: `/plugin marketplace add https://their-server/m/<slug>`.
6. Plugins appear in Claude Code and can be installed. The same git repo also contains Codex plugin manifests for skill-bearing plugins.

The user **never** sees, types, or learns git, even though git is the storage engine.

### Who this is for

Internal teams sharing **proprietary** business-process plugins. Single-tenant, behind a company's network or VPN. We are not building a public marketplace.

### Non-goals for v1

- LLM-assisted skill authoring
- LSP server, theme, channel, dependency, or userConfig authoring
- Anthropic Cowork ZIP export
- Approval workflows

---

## The multi-marketplace model

This is load-bearing.

A **marketplace** is the unit the user creates first and shares with collaborators. It maps 1:1 to what Claude Code calls a "plugin marketplace" — what you `/plugin marketplace add` to. A single SkillShelf instance hosts many marketplaces side by side.

Each marketplace has:
- A slug (URL-safe id, e.g. `finance-team-skills`)
- A display name
- An owner name and email (used as the git author when committing)
- A visibility (`workspace` or `restricted`)
- Its own git repo on disk
- Its own `marketplace.json` endpoint at `/m/<slug>` and `/m/<slug>/marketplace.json`
- Its own git smart-HTTP endpoint at `/m/<slug>/git/repo.git`
- A collection of plugins, each rendered as an installable plugin directory inside the repo
- Skill-bearing plugins also get Codex manifests; hooks, agents, MCP servers, commands, monitors, and settings are Claude-only in the current implementation

A plugin belongs to exactly one marketplace. A skill belongs to exactly one plugin. Cross-marketplace sharing is post-v1.

### Canonical user flow

```
User opens app
  └─ Empty state: "Create your first marketplace"
       └─ User creates "Finance Team Skills"
            └─ Lands on marketplace page
                 ├─ Shows the "Connect" snippet with the actual URL to copy
                 ├─ Empty plugin list with an "Add plugin" button
                 └─ Settings tab (rename, owner info, delete)
                      └─ User creates a plugin
                           └─ Adds skills, hooks, agents, MCP servers, commands, monitors, or settings
                                └─ Plugin appears in list
```

Top-level navigation always shows the list of marketplaces. Plugin and component management always happens inside a specific marketplace context.

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
skillshelf/
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
│   │   ├── config.py           # env loading (PORT, PUBLIC_BASE_URL, SKILLSHELF_DATA_DIR)
│   │   ├── db.py               # SQLAlchemy engine + session factory
│   │   ├── models.py           # Core Table objects (no ORM classes)
│   │   ├── schemas.py          # Pydantic request/response models
│   │   ├── routes/
│   │   │   ├── api_marketplaces.py
│   │   │   ├── api_plugins.py
│   │   │   ├── marketplace_public.py   # /m/{slug} endpoints
│   │   │   └── git_smart_http.py       # /m/{slug}/git/repo.git/*
│   │   └── lib/
│   │       ├── git_store.py
│   │       ├── slug.py
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
│       │   └── PluginEditor.tsx
│       └── components/
├── /var/lib/skillshelf/        # Runtime in container — mounted as a persistent volume
│   ├── marketplaces/
│   │   └── <slug>/
│   │       ├── repo/           # Bare git repo
│   │       └── working/        # Working tree
│   └── skillshelf.db
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
  visibility    TEXT NOT NULL DEFAULT 'workspace',
  created_at    INTEGER NOT NULL,
  updated_at    INTEGER NOT NULL
);

CREATE TABLE plugins (
  marketplace_slug  TEXT NOT NULL REFERENCES marketplaces(slug) ON DELETE CASCADE,
  slug              TEXT NOT NULL,
  display_name      TEXT NOT NULL,
  description       TEXT NOT NULL,
  version           TEXT NOT NULL DEFAULT '1.0.0',
  created_at        INTEGER NOT NULL,
  updated_at        INTEGER NOT NULL,
  last_commit       TEXT,
  PRIMARY KEY (marketplace_slug, slug)
);

CREATE TABLE skills (
  marketplace_slug  TEXT NOT NULL,
  plugin_slug       TEXT NOT NULL,
  slug              TEXT NOT NULL,
  display_name      TEXT NOT NULL,
  description       TEXT NOT NULL,
  version           TEXT NOT NULL DEFAULT '1.0.0',
  content           TEXT NOT NULL,
  created_at        INTEGER NOT NULL,
  updated_at        INTEGER NOT NULL,
  last_commit       TEXT,
  PRIMARY KEY (marketplace_slug, plugin_slug, slug),
  FOREIGN KEY (marketplace_slug, plugin_slug) REFERENCES plugins(marketplace_slug, slug) ON DELETE CASCADE
);
```

Component tables hang off `(marketplace_slug, plugin_slug)`:
- `plugin_hooks`: `event`, `matcher`, `handler_json`
- `plugin_agents`: `description`, `config_json`, `prompt`
- `plugin_mcp_servers`: `config_json`
- `plugin_commands`: `description`, `content`
- `plugin_monitors`: `command`, `description`, optional `when`
- `plugin_settings`: one JSON settings document per plugin

Access control tables store provider-neutral identity and local grants:
- `organizations`: tenant boundary; v1 self-hosted uses one default organization
- `organization_settings`: organization access mode (`public`, `authenticated`, or `restricted`) and marketplace creation policy
- `auth_providers`: organization-scoped GitHub/OIDC/trusted-header login provider metadata; client secrets stored as plaintext (same exposure surface as session keys and local-account password hashes)
- `local_account_credentials`: local-account password credentials and forced password-change state
- `users`, `groups`, and `user_groups`: organization-scoped identity records synced from sessions, trusted headers, or OIDC-style claims
- `organization_role_grants`: organization role grants; use `organization_admin`
- `marketplace_role_grants` and `plugin_role_grants`: organization-scoped local role grants for users or groups
- `access_tokens`: user-owned agent access token rows; tokens are read-only, tied to the owning user's current permissions, and revoked/rotated per user
- `audit_events`: reserved for access and destructive-action audit records

### On-disk layout inside a marketplace's git repo

```
<repo-working-root>/
├── .claude-plugin/
│   └── marketplace.json          # Claude Code marketplace format
├── .agents/
│   └── plugins/
│       └── marketplace.json      # Codex marketplace format (skill-bearing plugins only)
├── .github/
│   └── plugin/
│       └── marketplace.json      # GitHub Copilot marketplace format (all plugins)
└── plugins/
    └── <plugin-slug>/
        ├── .claude-plugin/
        │   └── plugin.json
        ├── .codex-plugin/              # only when plugin has skills
        │   └── plugin.json
        ├── plugin.json                 # GitHub Copilot plugin manifest (always present)
        ├── hooks/
        │   └── hooks.json
        ├── agents/
        │   └── <agent-slug>.md
        ├── .mcp.json
        ├── commands/
        │   └── <command-slug>.md
        ├── monitors/
        │   └── monitors.json
        ├── settings.json
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

Plugins are the installable unit. Claude Code consumers read `.claude-plugin/*` plus root-level plugin components. Codex consumers read `.agents/plugins/marketplace.json` plus each skill-bearing plugin's `.codex-plugin/plugin.json`; non-skill Claude components are not represented in Codex metadata. GitHub Copilot consumers read `.github/plugin/marketplace.json` (all plugins) plus each plugin's root-level `plugin.json`; Copilot supports skills, agents, hooks, and MCP servers but not commands, monitors, or settings.

---

## The marketplace.json contract

Served at `GET /m/<slug>` and `GET /m/<slug>/marketplace.json` (identical content, regenerated from DB on each request). Also committed to the repo at `.claude-plugin/marketplace.json` so the repo is consumable via `git clone`.

```json
{
  "name": "<slug>",
  "owner": { "name": "<owner_name>", "email": "<owner_email>" },
  "plugins": [
    {
      "name": "<plugin-slug>",
      "description": "<description>",
      "version": "<version>",
      "source": {
        "source": "url",
        "url": "<PUBLIC_BASE_URL>/m/<slug>/git/repo.git",
        "path": "plugins/<plugin-slug>"
      }
    }
  ]
}
```

**Use `source: "url"` + `path`**, not relative paths. Relative paths in a URL-distributed `marketplace.json` silently fail to resolve. This is documented Claude Code behavior.

Codex marketplace metadata is committed to `.agents/plugins/marketplace.json` in the same repo. It uses Codex's repo-local marketplace shape:

```json
{
  "name": "<slug>",
  "interface": { "displayName": "<display_name>" },
  "plugins": [
    {
      "name": "<plugin-slug>",
      "source": { "source": "local", "path": "./plugins/<plugin-slug>" },
      "policy": { "installation": "AVAILABLE", "authentication": "ON_INSTALL" },
      "category": "Productivity"
    }
  ]
}
```

Each skill-bearing plugin also has `.codex-plugin/plugin.json` with `name`, `version`, `description`, `skills: "./skills/"`, and interface metadata derived from the plugin.

GitHub Copilot marketplace metadata is committed to `.github/plugin/marketplace.json`. It uses a different shape with a `source` string (not object) and a `metadata` block:

```json
{
  "name": "<slug>",
  "owner": { "name": "<owner_name>", "email": "<owner_email>" },
  "metadata": { "description": "<display_name>", "version": "1.0.0" },
  "plugins": [
    { "name": "<plugin-slug>", "description": "...", "version": "...", "source": "./plugins/<plugin-slug>" }
  ]
}
```

Every plugin also gets a root-level `plugins/<plugin-slug>/plugin.json` for Copilot, with `name`, `version`, `description`, `author`, `license: "proprietary"`, and optional `skills`, `agents`, `hooks`, `mcpServers` fields (omitted when absent). Copilot does not use commands, monitors, or settings. Users register a Copilot marketplace with: `copilot plugin marketplace add <PUBLIC_BASE_URL>/m/<slug>/git/repo.git`.

---

## API surface

All under `/api`, JSON in / JSON out. Access is controlled by organization mode and local role grants.

### Marketplaces

| Method | Path | Notes |
|---|---|---|
| `GET` | `/api/marketplaces` | List all |
| `GET` | `/api/marketplaces/{slug}` | One + skill/plugin counts |
| `POST` | `/api/marketplaces` | Body: `displayName, ownerName, ownerEmail`; server derives slug; 409 on collision |
| `PUT` | `/api/marketplaces/{slug}` | Partial update; cannot change slug; can update `visibility` |
| `DELETE` | `/api/marketplaces/{slug}` | Cascades to plugins/components, removes on-disk repo |

### Access controls

| Method | Path | Notes |
|---|---|---|
| `GET` | `/api/me` | Current user from session or trusted identity headers |
| `GET` | `/api/organization/settings` | Organization access mode and marketplace creation policy |
| `PUT` | `/api/organization/settings` | Organization-admin only; mode is `public`, `authenticated`, or `restricted` |
| `GET/POST/PUT/DELETE` | `/api/organization/auth-providers` | Organization-admin login provider metadata; PUT without `clientSecret` preserves stored value |
| `GET` | `/api/audit-events` | Organization-admin audit event list; supports `limit`, `action`, `targetType`, and `actorUserId` filters |
| `GET/POST/DELETE` | `/api/marketplaces/{slug}/grants` | Marketplace-admin grant management for users/groups |
| `GET` | `/api/agent-access` | Returns/creates the signed-in user's agent access token for authenticated snippets |
| `POST` | `/api/agent-access/rotate` | Revokes the signed-in user's previous agent access and creates a new token |

Roles are `organization_admin`, `marketplace_admin`, `marketplace_maintainer`, `marketplace_contributor`, optional `plugin_maintainer`, and `viewer`. `viewer` is read-only for restricted marketplaces, `marketplace_contributor` can create and edit marketplace plugins/components, `marketplace_maintainer` can also delete marketplace plugins/components, and `marketplace_admin` manages marketplace settings, people, and deletion. In `public` mode, anonymous users can read workspace-visible marketplaces and smart-HTTP repos, but writes still require a real authenticated user with the right grant. In `authenticated` mode, organization-visible marketplaces require a signed-in user. In `restricted` mode, marketplace reads require an explicit grant or user-owned agent access token whose owning user still has read permission.

Lifecycle phases:
- **Pre-setup**: `organizations.bootstrap_completed_at IS NULL`; `/setup` is open and the first successful `POST /api/organization/setup` creates the initial auth provider and organization admin. A concurrent second setup returns 409.
- **Operational**: `bootstrap_completed_at` is set; `/setup` is locked, `/login` is live, and anonymous admin behavior is not available.

Recovery is via host-shell CLI: `python -m skillshelf reset-password <email>`, `python -m skillshelf promote-user <email> organization_admin`, and `python -m skillshelf create-user <email> <display-name>`.

Manual Auth0 validation target:
- Configure Auth0 as an OIDC provider with callback URL `<PUBLIC_BASE_URL>/auth/callback/<provider-slug>`.
- The authorization request must use scopes containing `openid email profile`.
- The userinfo response must include `sub` and `email`; `name` is optional and falls back to email.
- If group-gated access is tested, configure the SkillShelf provider `groupClaim` to the exact Auth0 custom claim key and ensure that claim returns a string or list of group names matching `allowlist.allowedGroups`.
- Disabled SkillShelf users and users outside `allowedGroups` must be denied on the next login attempt.

### Plugins and components

| Method | Path | Notes |
|---|---|---|
| `GET` | `/api/marketplaces/{slug}/plugins` | List plugins with component counts |
| `GET` | `/api/marketplaces/{slug}/plugins/{plugin_slug}` | One plugin with component counts |
| `POST` | `/api/marketplaces/{slug}/plugins` | Body: `displayName, description`; server derives plugin slug |
| `PUT` | `/api/marketplaces/{slug}/plugins/{plugin_slug}` | Partial update; bumps patch version |
| `DELETE` | `/api/marketplaces/{slug}/plugins/{plugin_slug}` | Cascades to components and removes plugin files |

Nested component paths hang off `/api/marketplaces/{slug}/plugins/{plugin_slug}`:
- `/skills`
- `/hooks`
- `/agents`
- `/mcp-servers`
- `/commands`
- `/monitors`
- `/settings`

There are no top-level skill shortcut endpoints. Skills are always managed under `/api/marketplaces/{slug}/plugins/{plugin_slug}/skills`.

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
4. Write / remove files in `<SKILLSHELF_DATA_DIR>/marketplaces/<slug>/working/`.
5. Regenerate `.claude-plugin/marketplace.json` and `.agents/plugins/marketplace.json` in the working tree from current DB state — always full rewrite, never patch.
6. `git_store.commit(...)` — **single dulwich commit** containing component files, Claude manifests, Codex manifests, and regenerated marketplace files.
7. Update `last_commit` on affected plugin rows, and affected skill rows when the mutation touches skills.
8. `COMMIT` the SQLAlchemy transaction.

On any exception in steps 4–7: SQLAlchemy rolls back; explicitly reset the working tree from the bare repo via dulwich (file-system writes are not covered by the DB transaction rollback).

Atomicity is non-negotiable. A `git clone` between two commits should never see either marketplace file disagree with the plugin folders.

---

## Self-verification loop

**Run `python scripts/verify.py` before declaring any task complete.** Don't ask the human. Don't move on if it fails. Fix it first.

### What `scripts/verify.py` does (all 12 steps must pass)

1. Start the FastAPI server on a random free port with a temporary `SKILLSHELF_DATA_DIR`.
2. Assert setup is required, complete `/api/organization/setup` with Local Accounts, verify a real admin session, and assert a second setup returns 409.
3. `POST /api/marketplaces` → create "Finance Team Skills".
3. `GET /m/finance-team-skills/marketplace.json` → assert valid JSON, empty `plugins`, correct `name`/`owner`.
4. `POST /api/marketplaces/finance-team-skills/plugins`, then `POST /api/marketplaces/finance-team-skills/plugins/quarterly-report-process/skills` → create "Quarterly Report Process".
5. Re-fetch `marketplace.json` → assert skill appears with correct `source.url`, `source.path`, `description`.
6. `dulwich.porcelain.clone` from `http://localhost:<port>/m/finance-team-skills/git/repo.git` into a temp dir.
7. Assert cloned repo contains the expected Claude and Codex files (§ on-disk layout) with correct content.
8. `PUT` an edit to the skill's content. Re-clone. Assert updated content and Codex plugin version.
9. `DELETE` the plugin. Re-fetch `marketplace.json` → plugin gone. Re-clone → plugin folder gone.
10. Create a second marketplace + skill. Assert it has its own `/m/<slug>` and git repo, fully isolated.
11. Create a multi-capability plugin with a skill, hook, agent, MCP server, command, monitor, and settings. Clone and assert every component file is rendered at the plugin root-level paths Claude expects.
12. `DELETE` the first marketplace. Assert its endpoints return 404 and its on-disk repo is removed. Assert second marketplace is untouched.
13. Clear the session and assert anonymous writes return 401; verify local login, wrong-password failure, admin-created users with forced password change, and recovery CLI reset-password, then shut down server.
Exit 0 on success, non-zero with diff/log on failure.

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

### Commit discipline

Make **atomic commits** as part of implementation — one commit per logical unit of work. Do not batch everything into a single end-of-task commit and do not wait to be asked. Typical split for a feature:

1. Shared infrastructure first (extracted components, new utilities).
2. New feature code.
3. Refactors or renames that follow from it (e.g., updated routes/links).

Follow the imperative style already in the repo history: `Add X`, `Extract Y`, `Move Z to …`.

---

## Things easy to get wrong

- **`marketplace.json` byte-for-byte conformance.** Claude Code parses this strictly. Use `source: "url"` + `path`, never relative paths.
- **Slug derivation.** NFKD strip accents, lowercase, collapse non-alphanumerics to single dashes, trim leading/trailing dashes, cap at 64 chars. Test: `"Q4 — Sales Report 📊"` → `q4-sales-report`. On collision, return 409 — **do not auto-suffix**.
- **`source.path` uses forward slashes on all platforms.** Never `os.path.join` for this field. Use `posixpath.join` or template strings.
- **Skill files plus Claude and Codex marketplace/plugin manifests go in the same dulwich commit.** Splitting them produces inconsistent clones.
- **No subprocess to git.** Container must not need a git binary. dulwich only.
- **`PUBLIC_BASE_URL` is the most important config.** If it's wrong, every `source.url` in every `marketplace.json` is unreachable. Log it on startup. Warn if it points at `localhost` outside dev mode.
- **Working-tree cleanup on failure.** File-system writes are not covered by the SQLAlchemy rollback. Must explicitly reset the working tree from the bare repo when steps 4–7 of the write path fail.

---

## Configuration

```
PORT=3000
PUBLIC_BASE_URL=http://localhost:3000   # CRITICAL — embedded in marketplace.json
SKILLSHELF_DATA_DIR=/var/lib/skillshelf
NODE_ENV=development
```

Loaded by `backend/app/config.py` using Pydantic `BaseSettings`. Log `PUBLIC_BASE_URL` on startup. Warn loudly if it contains `localhost` and `NODE_ENV != development`.

---

## Manual acceptance test

The verify harness covers everything except the actual Claude Code client. Before declaring v1 done, the human runs this checklist:

1. `docker compose up`.
2. Open the UI. Create a marketplace called "Hello Marketplace."
3. The marketplace detail page shows a `/plugin marketplace add ...` snippet.
4. Create a plugin called "Hello World", then add a skill with description "A test skill" and content "Say hello to the user when asked."
5. In Claude Code: run the snippet from step 3. Then `/plugin install hello-world@hello-marketplace`.
6. Start a new Claude Code session. Ask "say hello." The skill activates.
7. Edit the skill in the UI. Run `/plugin marketplace update` in Claude Code. The new content takes effect.
8. Delete the plugin. Run `/plugin marketplace update`. The plugin is gone.
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
