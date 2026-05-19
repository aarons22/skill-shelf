"""
SkillForge self-verification harness (§10).

Starts the server on a random free port, exercises the full product
end-to-end (HTTP API + real git clone via dulwich), then shuts down.

Exit 0 on success. Exit 1 with a detailed log on any failure.
"""
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx
from dulwich import porcelain

# Ensure we can import from the backend directory
REPO_ROOT = Path(__file__).parent.parent
BACKEND_DIR = REPO_ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_for_server(base_url: str, timeout: float = 15.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = httpx.get(f"{base_url}/health", timeout=1)
            if r.status_code == 200:
                return
        except Exception:
            pass
        time.sleep(0.1)
    raise RuntimeError(f"Server at {base_url} did not start within {timeout}s")


def clone_repo(url: str, target_dir: str) -> None:
    """Clone via dulwich (no git binary)."""
    if os.path.exists(target_dir):
        import shutil
        shutil.rmtree(target_dir)
    porcelain.clone(url, target_dir, checkout=True)


def assert_file_contains(path: str, substring: str) -> None:
    content = Path(path).read_text()
    if substring not in content:
        raise AssertionError(
            f"Expected {substring!r} in {path}\nActual content:\n{content}"
        )


def assert_file_missing(path: str) -> None:
    if os.path.exists(path):
        raise AssertionError(f"Expected {path} to not exist, but it does")


def run_verification() -> None:
    port = free_port()
    base_url = f"http://127.0.0.1:{port}"

    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = os.path.join(tmpdir, "data")
        os.makedirs(os.path.join(data_dir, "marketplaces"), exist_ok=True)

        env = {
            **os.environ,
            "DATA_DIR": data_dir,
            "PUBLIC_BASE_URL": base_url,
            "PORT": str(port),
            "NODE_ENV": "development",
        }

        print(f"[verify] Starting server on port {port} with DATA_DIR={data_dir}")
        proc = subprocess.Popen(
            [
                str(BACKEND_DIR / ".venv" / "bin" / "uvicorn"),
                "app.main:app",
                "--host", "127.0.0.1",
                "--port", str(port),
                "--log-level", "warning",
            ],
            cwd=str(BACKEND_DIR),
            env=env,
        )

        try:
            wait_for_server(base_url)
            print(f"[verify] Server up at {base_url}")

            client = httpx.Client(base_url=base_url)

            # ── Step 2: Create "Finance Team Skills" ──────────────────────────
            print("[verify] Step 2: POST /api/marketplaces")
            r = client.post("/api/marketplaces", json={
                "displayName": "Finance Team Skills",
                "ownerName": "Test Owner",
                "ownerEmail": "owner@example.com",
            })
            assert r.status_code == 201, f"Step 2 failed: {r.status_code} {r.text}"
            assert r.json()["slug"] == "finance-team-skills"
            print(f"  slug = {r.json()['slug']}")

            # ── Step 3: GET marketplace.json — empty plugins ──────────────────
            print("[verify] Step 3: GET /m/finance-team-skills/marketplace.json")
            r = client.get("/m/finance-team-skills/marketplace.json")
            assert r.status_code == 200, f"Step 3 failed: {r.status_code} {r.text}"
            mj = r.json()
            assert mj["name"] == "finance-team-skills"
            assert mj["owner"]["name"] == "Test Owner"
            assert mj["owner"]["email"] == "owner@example.com"
            assert mj["plugins"] == [], f"Expected empty plugins, got {mj['plugins']}"
            print(f"  name={mj['name']}, plugins=[]  ✓")

            # ── Step 4: Create plugin + skill "Quarterly Report Process" ─────
            print("[verify] Step 4: POST plugin + skill")
            r = client.post("/api/marketplaces/finance-team-skills/plugins", json={
                "displayName": "Quarterly Report Process",
                "description": "Guides the quarterly reporting workflow",
            })
            assert r.status_code == 201, f"Step 4 plugin create failed: {r.status_code} {r.text}"
            assert r.json()["slug"] == "quarterly-report-process"
            r = client.post("/api/marketplaces/finance-team-skills/plugins/quarterly-report-process/skills", json={
                "displayName": "Quarterly Report Process",
                "description": "Guides the quarterly reporting workflow",
                "content": "Follow these steps for quarterly reporting.",
            })
            assert r.status_code == 201, f"Step 4 skill create failed: {r.status_code} {r.text}"
            skill_data = r.json()
            assert skill_data["slug"] == "quarterly-report-process"
            print(f"  skill slug = {skill_data['slug']}")

            # ── Step 5: Re-fetch marketplace.json — skill appears ─────────────
            print("[verify] Step 5: Re-fetch marketplace.json with skill")
            r = client.get("/m/finance-team-skills")
            assert r.status_code == 200, f"Step 5 GET failed: {r.status_code}"
            mj = r.json()
            assert len(mj["plugins"]) == 1, f"Expected 1 plugin, got {mj['plugins']}"
            plugin = mj["plugins"][0]
            assert plugin["name"] == "quarterly-report-process"
            assert plugin["description"] == "Guides the quarterly reporting workflow"
            assert plugin["source"]["source"] == "url"
            assert plugin["source"]["url"] == f"{base_url}/m/finance-team-skills/git/repo.git"
            assert plugin["source"]["path"] == "plugins/quarterly-report-process"
            assert "\\" not in plugin["source"]["path"], "Backslash in source.path!"
            print(f"  plugin.source.url = {plugin['source']['url']}  ✓")
            print(f"  plugin.source.path = {plugin['source']['path']}  ✓")

            # ── Step 6: Clone the repo ────────────────────────────────────────
            clone_dir = os.path.join(tmpdir, "clone1")
            git_url = f"{base_url}/m/finance-team-skills/git/repo.git"
            print(f"[verify] Step 6: clone {git_url}")
            clone_repo(git_url, clone_dir)
            print("  Clone succeeded  ✓")

            # ── Step 7: Assert §6 on-disk layout ─────────────────────────────
            print("[verify] Step 7: Assert on-disk layout")
            mj_path = os.path.join(clone_dir, ".claude-plugin", "marketplace.json")
            assert os.path.exists(mj_path), f"Missing {mj_path}"
            mj_content = json.loads(Path(mj_path).read_text())
            assert mj_content["name"] == "finance-team-skills"
            assert len(mj_content["plugins"]) == 1

            codex_mj_path = os.path.join(clone_dir, ".agents", "plugins", "marketplace.json")
            assert os.path.exists(codex_mj_path), f"Missing {codex_mj_path}"
            codex_mj = json.loads(Path(codex_mj_path).read_text())
            assert codex_mj["name"] == "finance-team-skills"
            assert codex_mj["interface"]["displayName"] == "Finance Team Skills"
            assert codex_mj["plugins"][0]["source"] == {
                "source": "local",
                "path": "./plugins/quarterly-report-process",
            }
            assert codex_mj["plugins"][0]["policy"] == {
                "installation": "AVAILABLE",
                "authentication": "ON_INSTALL",
            }

            plugin_dir = os.path.join(clone_dir, "plugins", "quarterly-report-process")
            plugin_json = os.path.join(plugin_dir, ".claude-plugin", "plugin.json")
            codex_plugin_json = os.path.join(plugin_dir, ".codex-plugin", "plugin.json")
            skill_md = os.path.join(plugin_dir, "skills", "quarterly-report-process", "SKILL.md")
            assert os.path.exists(plugin_json), f"Missing {plugin_json}"
            assert os.path.exists(codex_plugin_json), f"Missing {codex_plugin_json}"
            codex_plugin = json.loads(Path(codex_plugin_json).read_text())
            assert codex_plugin["name"] == "quarterly-report-process"
            assert codex_plugin["version"] == "1.0.1", f"Expected 1.0.1 got {codex_plugin['version']}"
            assert codex_plugin["skills"] == "./skills/"
            assert os.path.exists(skill_md), f"Missing {skill_md}"
            assert_file_contains(skill_md, "quarterly-report-process")
            assert_file_contains(skill_md, "Guides the quarterly reporting workflow")
            assert_file_contains(skill_md, "Follow these steps for quarterly reporting.")
            print("  §6 layout correct  ✓")

            # ── Step 8: PUT edit, re-clone, assert updated content ────────────
            print("[verify] Step 8: PUT skill update, re-clone")
            r = client.put("/api/marketplaces/finance-team-skills/plugins/quarterly-report-process/skills/quarterly-report-process", json={
                "content": "UPDATED: The new quarterly process."
            })
            assert r.status_code == 200, f"Step 8 PUT failed: {r.status_code} {r.text}"
            assert r.json()["version"] == "1.0.1", f"Expected skill 1.0.1 got {r.json()['version']}"

            clone_dir2 = os.path.join(tmpdir, "clone2")
            clone_repo(git_url, clone_dir2)
            skill_md2 = os.path.join(clone_dir2, "plugins", "quarterly-report-process",
                                     "skills", "quarterly-report-process", "SKILL.md")
            assert_file_contains(skill_md2, "UPDATED: The new quarterly process.")
            codex_plugin2_path = os.path.join(
                clone_dir2,
                "plugins",
                "quarterly-report-process",
                ".codex-plugin",
                "plugin.json",
            )
            codex_plugin2 = json.loads(Path(codex_plugin2_path).read_text())
            assert codex_plugin2["version"] == "1.0.2", f"Expected plugin 1.0.2 got {codex_plugin2['version']}"
            print("  Updated content in re-clone  ✓")

            # ── Step 9: DELETE plugin, assert gone from JSON and repo ─────────
            print("[verify] Step 9: DELETE plugin")
            r = client.delete("/api/marketplaces/finance-team-skills/plugins/quarterly-report-process")
            assert r.status_code == 204, f"Step 9 DELETE failed: {r.status_code}"

            r = client.get("/m/finance-team-skills")
            assert r.json()["plugins"] == [], f"Expected empty plugins after delete, got {r.json()['plugins']}"

            clone_dir3 = os.path.join(tmpdir, "clone3")
            clone_repo(git_url, clone_dir3)
            assert_file_missing(os.path.join(clone_dir3, "plugins", "quarterly-report-process"))
            print("  Skill absent from re-clone  ✓")

            # ── Step 10: Second marketplace — fully isolated ──────────────────
            print("[verify] Step 10: Create second marketplace")
            r = client.post("/api/marketplaces", json={
                "displayName": "Engineering Runbooks",
                "ownerName": "Eng Owner",
                "ownerEmail": "eng@example.com",
            })
            assert r.status_code == 201
            assert r.json()["slug"] == "engineering-runbooks"

            r = client.post("/api/marketplaces/engineering-runbooks/plugins", json={
                "displayName": "Deploy Process",
                "description": "How to deploy",
            })
            assert r.status_code == 201
            r = client.post("/api/marketplaces/engineering-runbooks/plugins/deploy-process/skills", json={
                "displayName": "Deploy Process",
                "description": "How to deploy",
                "content": "Run the deploy script.",
            })
            assert r.status_code == 201

            r_eng = client.get("/m/engineering-runbooks")
            assert r_eng.status_code == 200
            assert len(r_eng.json()["plugins"]) == 1
            assert r_eng.json()["plugins"][0]["name"] == "deploy-process"

            r_fin = client.get("/m/finance-team-skills")
            assert r_fin.json()["plugins"] == [], "Finance marketplace polluted by Engineering skills"

            eng_clone = os.path.join(tmpdir, "eng_clone")
            eng_git_url = f"{base_url}/m/engineering-runbooks/git/repo.git"
            clone_repo(eng_git_url, eng_clone)
            assert os.path.exists(os.path.join(eng_clone, "plugins", "deploy-process"))
            assert_file_missing(os.path.join(eng_clone, "plugins", "quarterly-report-process"))
            print("  Second marketplace isolated  ✓")

            # ── Step 10b: Multi-capability plugin rendering ───────────────────
            print("[verify] Step 10b: Create multi-capability plugin")
            r = client.post("/api/marketplaces/engineering-runbooks/plugins", json={
                "displayName": "Ops Toolkit",
                "description": "Operational Claude plugin components",
            })
            assert r.status_code == 201, f"Plugin create failed: {r.status_code} {r.text}"

            r = client.post("/api/marketplaces/engineering-runbooks/plugins/ops-toolkit/skills", json={
                "displayName": "Incident Triage",
                "description": "Triage incidents",
                "content": "Follow the incident checklist.",
            })
            assert r.status_code == 201, f"Plugin skill create failed: {r.status_code} {r.text}"
            r = client.post("/api/marketplaces/engineering-runbooks/plugins/ops-toolkit/hooks", json={
                "displayName": "Format on edit",
                "event": "PostToolUse",
                "matcher": "Write|Edit",
                "handler": {
                    "type": "command",
                    "command": "${CLAUDE_PLUGIN_ROOT}/scripts/format.sh",
                    "args": [],
                    "timeout": 30,
                },
                "unsafeConfirmed": True,
            })
            assert r.status_code == 201, f"Hook create failed: {r.status_code} {r.text}"
            r = client.post("/api/marketplaces/engineering-runbooks/plugins/ops-toolkit/agents", json={
                "displayName": "Reviewer",
                "description": "Reviews operational changes",
                "prompt": "Review the change.",
                "config": {"model": "sonnet", "maxTurns": 5},
            })
            assert r.status_code == 201, f"Agent create failed: {r.status_code} {r.text}"
            r = client.post("/api/marketplaces/engineering-runbooks/plugins/ops-toolkit/mcp-servers", json={
                "displayName": "Status API",
                "config": {"type": "http", "url": "https://status.example.com/mcp"},
                "unsafeConfirmed": True,
            })
            assert r.status_code == 201, f"MCP create failed: {r.status_code} {r.text}"
            r = client.post("/api/marketplaces/engineering-runbooks/plugins/ops-toolkit/commands", json={
                "displayName": "Deploy",
                "description": "Deploy safely",
                "content": "Deploy with $ARGUMENTS.",
            })
            assert r.status_code == 201, f"Command create failed: {r.status_code} {r.text}"
            r = client.post("/api/marketplaces/engineering-runbooks/plugins/ops-toolkit/monitors", json={
                "displayName": "Error Log",
                "command": "tail -F ./logs/error.log",
                "description": "Application error log",
                "when": "always",
                "unsafeConfirmed": True,
            })
            assert r.status_code == 201, f"Monitor create failed: {r.status_code} {r.text}"
            r = client.put("/api/marketplaces/engineering-runbooks/plugins/ops-toolkit/settings", json={
                "settings": {"agent": "reviewer"},
            })
            assert r.status_code == 200, f"Settings save failed: {r.status_code} {r.text}"

            r_eng = client.get("/m/engineering-runbooks")
            plugin_names = [p["name"] for p in r_eng.json()["plugins"]]
            assert plugin_names == ["deploy-process", "ops-toolkit"], plugin_names
            ops_entry = [p for p in r_eng.json()["plugins"] if p["name"] == "ops-toolkit"][0]
            assert ops_entry["source"]["path"] == "plugins/ops-toolkit"

            eng_clone2 = os.path.join(tmpdir, "eng_clone_multi")
            clone_repo(eng_git_url, eng_clone2)
            ops_dir = os.path.join(eng_clone2, "plugins", "ops-toolkit")
            claude_manifest = json.loads(Path(os.path.join(ops_dir, ".claude-plugin", "plugin.json")).read_text())
            assert claude_manifest["skills"] == "./skills/"
            assert claude_manifest["hooks"] == "./hooks/hooks.json"
            assert claude_manifest["agents"] == "./agents/"
            assert claude_manifest["mcpServers"] == "./.mcp.json"
            assert claude_manifest["commands"] == "./commands/"
            assert claude_manifest["experimental"]["monitors"] == "./monitors/monitors.json"
            assert_file_contains(os.path.join(ops_dir, "skills", "incident-triage", "SKILL.md"), "Follow the incident checklist.")
            hooks_json = json.loads(Path(os.path.join(ops_dir, "hooks", "hooks.json")).read_text())
            assert hooks_json["hooks"]["PostToolUse"][0]["matcher"] == "Write|Edit"
            assert_file_contains(os.path.join(ops_dir, "agents", "reviewer.md"), "maxTurns: 5")
            mcp_json = json.loads(Path(os.path.join(ops_dir, ".mcp.json")).read_text())
            assert mcp_json["mcpServers"]["status-api"]["type"] == "http"
            assert_file_contains(os.path.join(ops_dir, "commands", "deploy.md"), "Deploy with $ARGUMENTS.")
            monitors_json = json.loads(Path(os.path.join(ops_dir, "monitors", "monitors.json")).read_text())
            assert monitors_json[0]["name"] == "error-log"
            settings_json = json.loads(Path(os.path.join(ops_dir, "settings.json")).read_text())
            assert settings_json["agent"] == "reviewer"
            print("  Multi-capability plugin layout correct  ✓")

            # ── Step 11: DELETE first marketplace ────────────────────────────
            print("[verify] Step 11: DELETE finance-team-skills")
            r = client.delete("/api/marketplaces/finance-team-skills")
            assert r.status_code == 204

            r = client.get("/m/finance-team-skills")
            assert r.status_code == 404, f"Expected 404 after delete, got {r.status_code}"

            r = client.get("/api/marketplaces/finance-team-skills")
            assert r.status_code == 404

            # Assert on-disk repo is gone
            fin_repo = os.path.join(data_dir, "marketplaces", "finance-team-skills")
            assert not os.path.exists(fin_repo), f"On-disk repo still exists at {fin_repo}"

            # Second marketplace unaffected
            r = client.get("/m/engineering-runbooks")
            assert r.status_code == 200
            assert len(r.json()["plugins"]) == 2
            eng_repo = os.path.join(data_dir, "marketplaces", "engineering-runbooks")
            assert os.path.isdir(eng_repo), "Engineering repo was unexpectedly deleted"
            print("  First deleted, second unaffected  ✓")

            print("\n[verify] ✅ ALL 12 STEPS PASSED")

        finally:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()


if __name__ == "__main__":
    try:
        run_verification()
        sys.exit(0)
    except AssertionError as e:
        print(f"\n[verify] ❌ ASSERTION FAILED:\n  {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        import traceback
        print(f"\n[verify] ❌ ERROR: {e}", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)
