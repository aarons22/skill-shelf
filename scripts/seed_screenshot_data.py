"""
Seed realistic demo data into the screenshot Docker environment.

Creates two marketplaces with plugins and skills that look compelling in a
product screenshot. The target instance must be freshly started (no existing
setup); this script completes the setup flow itself.

Usage:
    python3 scripts/seed_screenshot_data.py [BASE_URL]

Default BASE_URL: http://localhost:8899
"""

import sys
import time

try:
    import httpx
except ImportError:
    print("httpx is required. Activate the backend venv or run: pip install httpx", file=sys.stderr)
    sys.exit(1)

BASE_URL = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://localhost:8899"


def wait_for_health(timeout: float = 90.0) -> None:
    print(f"Waiting for {BASE_URL} to become healthy", end="", flush=True)
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = httpx.get(f"{BASE_URL}/health", timeout=2)
            if r.status_code == 200:
                print(" ✓")
                return
        except Exception:
            pass
        print(".", end="", flush=True)
        time.sleep(2)
    raise RuntimeError(f"Server at {BASE_URL} did not become healthy within {timeout}s")


def plugin(client: httpx.Client, marketplace_slug: str, display_name: str, description: str, content: str) -> None:
    r = client.post(f"/api/marketplaces/{marketplace_slug}/plugins", json={
        "displayName": display_name,
        "description": description,
    })
    assert r.status_code == 201, f"Plugin create failed ({display_name}): {r.status_code} {r.text}"
    slug = r.json()["slug"]

    r = client.post(f"/api/marketplaces/{marketplace_slug}/plugins/{slug}/skills", json={
        "displayName": display_name,
        "description": description,
        "content": content,
    })
    assert r.status_code == 201, f"Skill create failed ({display_name}): {r.status_code} {r.text}"
    print(f"  {display_name}  ✓")


def main() -> None:
    wait_for_health()

    client = httpx.Client(base_url=BASE_URL)

    print("Completing setup ...")
    r = client.post("/api/organization/setup", json={
        "displayName": "SkillShelf Demo",
        "accessMode": "public",
        "marketplaceCreation": "authenticated",
        "provider": {
            "provider": "local",
            "admin": {
                "email": "admin@example.com",
                "displayName": "Demo Admin",
                "password": "screenshot-demo-pass",
            },
        },
    })
    assert r.status_code == 200, f"Setup failed: {r.status_code} {r.text}"
    print("  Admin session ready  ✓")

    # ── Engineering Tools ────────────────────────────────────────────────────
    print("\nCreating 'Engineering Tools' marketplace ...")
    r = client.post("/api/marketplaces", json={"displayName": "Engineering Tools"})
    assert r.status_code == 201, f"Marketplace create failed: {r.status_code} {r.text}"

    plugin(client, "engineering-tools",
           "Code Review",
           "Review changed files for bugs, security issues, and style violations",
           "Examine the diff for correctness, security vulnerabilities, and adherence to team style. "
           "Flag issues by severity: critical, warning, or suggestion.")

    plugin(client, "engineering-tools",
           "Git Workflow",
           "Generate commit messages, branch names, and pull request descriptions",
           "Follow conventional commits (feat/fix/chore/docs). Branch names use kebab-case with a "
           "type prefix. PR descriptions include a summary, test plan, and screenshot if UI changed.")

    plugin(client, "engineering-tools",
           "Documentation",
           "Generate API docs, README sections, and inline comments from code",
           "Write documentation that explains the why, not just the what. Prefer examples over "
           "prose. Keep README sections short and scannable.")

    # ── Finance Team Skills ──────────────────────────────────────────────────
    print("\nCreating 'Finance Team Skills' marketplace ...")
    r = client.post("/api/marketplaces", json={"displayName": "Finance Team Skills"})
    assert r.status_code == 201, f"Marketplace create failed: {r.status_code} {r.text}"

    plugin(client, "finance-team-skills",
           "Quarterly Report",
           "Guide the full quarterly reporting workflow from data collection to executive summary",
           "Walk through: (1) pull actuals from the data warehouse, (2) compute variance vs budget, "
           "(3) draft the narrative, (4) format for the board deck.")

    plugin(client, "finance-team-skills",
           "Budget Analysis",
           "Analyze budget vs actuals, flag variances, and suggest reallocations",
           "Compare each budget line to actuals. Flag variances > 10% for review. "
           "Propose reallocation options with rationale.")

    plugin(client, "finance-team-skills",
           "Compliance Checker",
           "Verify reports and documents against regulatory requirements and internal policy",
           "Check for required disclosures, correct formatting, and policy compliance. "
           "Output a checklist with pass/fail status for each requirement.")

    print(f"\nSeed complete. Screenshot environment ready at {BASE_URL}")
    print(f"  List page:   {BASE_URL}/")
    print(f"  Detail page: {BASE_URL}/marketplaces/engineering-tools")


if __name__ == "__main__":
    main()
