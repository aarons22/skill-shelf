# SkillShelf

SkillShelf is a self-hostable web app for creating and managing plugin marketplaces for Claude Code, GitHub Copilot, and Codex. Teams create a marketplace, add installable plugins, attach guided components, and share one URL without asking plugin authors to touch git.

<p align="center">
  <img src="docs/assets/screenshot-list.png" alt="SkillShelf showing two team marketplaces — Engineering Tools and Finance Team Skills" width="900" />
</p>

<p align="center">
  <img src="docs/assets/screenshot-detail.png" alt="Engineering Tools marketplace showing install snippets for Claude Code, GitHub Copilot, and Codex alongside plugin cards with one-line install commands" width="900" />
</p>

## Quick Start

Requirements:

- Docker
- Docker Compose

```sh
cp .env.example .env
docker compose up --build
```

Open the app at:

```text
http://localhost/
```

Set `PUBLIC_BASE_URL` in `.env` to the URL your AI coding agents can reach. SkillShelf embeds this value in every `marketplace.json`, so production deployments should use the public HTTPS origin.

## Basic Use

1. Open SkillShelf. On a fresh install, complete the `/setup` wizard — the first user becomes organization admin.
2. Create a marketplace for a team or workflow area.
3. Create a plugin inside that marketplace.
4. Add components to the plugin: skills, hooks, agents, MCP servers, commands, monitors, or default settings.
5. Copy the connect snippet for your AI coding agent from the marketplace page.

**Claude Code**
```text
/plugin marketplace add https://your-server.example.com/m/<marketplace-slug>
```

**GitHub Copilot**
```text
copilot plugin marketplace add https://your-server.example.com/m/<marketplace-slug>/git/repo.git
```

**Codex**

Add the marketplace URL to your Codex configuration. The repo at `/m/<marketplace-slug>/git/repo.git` contains Codex-compatible metadata for all skill-bearing plugins.

6. Install individual plugins from the marketplace inside your agent.

### Component compatibility

| Component | Claude Code | GitHub Copilot | Codex |
|---|:---:|:---:|:---:|
| Skills | ✓ | ✓ | ✓ |
| Agents | ✓ | ✓ | — |
| Hooks | ✓ | ✓ | — |
| MCP Servers | ✓ | ✓ | — |
| Commands | ✓ | — | — |
| Monitors | ✓ | — | — |
| Settings | ✓ | — | — |

## Deployment

The default Docker Compose setup stores SQLite metadata and per-marketplace git repos in a named Docker volume mounted at `/var/lib/skillshelf`.

For production, put SkillShelf behind HTTPS and set:

```sh
PUBLIC_BASE_URL=https://your-server.example.com
SKILLSHELF_DATA_DIR=/var/lib/skillshelf
NODE_ENV=production
SKILLSHELF_SESSION_SECRET=<long-random-secret>
```

Organization admins configure login providers at `/organization/auth`. Provider client secrets are entered directly in the admin UI and stored in SQLite alongside other credentials (session keys and local-account password hashes).

When running the backend directly for local development, use a writable local path such as `SKILLSHELF_DATA_DIR=../.skillshelf-data`.

See [Deployment](docs/DEPLOYMENT.md) for volume, reverse proxy, and backup notes.

## Security

SkillShelf is currently intended for trusted internal networks and trusted plugin authors. Hooks, MCP servers, and monitors may execute commands on users' machines after installation, so do not expose a v1 deployment as a public marketplace.

## Roadmap

- Multi-organization SaaS features such as organization switching, membership lifecycle, and billing.
- Audit logs and approval workflows for plugin changes.
- Safer review and signing flows for executable components like hooks, MCP servers, and monitors.
- Cloud deployment hardening: backups, restore docs, health checks, metrics, and managed storage options.
- Claude Code client acceptance testing beyond the automated verification harness.

SkillShelf is not a replacement for Claude skills or MCP servers. It is the management and distribution layer that packages those artifacts into Claude Code-, GitHub Copilot-, and Codex-compatible plugin marketplaces.

## Development

Development setup, test commands, and the verification harness live in [Development](docs/DEVELOPMENT.md).

## License

SkillShelf is licensed under [Apache-2.0](LICENSE), a permissive license with an explicit patent grant.
