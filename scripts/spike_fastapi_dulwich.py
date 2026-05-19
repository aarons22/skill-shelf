"""
Spike: Mount dulwich WSGI app inside FastAPI.
Tries a2wsgi first (recommended replacement for deprecated starlette WSGIMiddleware).
"""
import os
import sys
import tempfile
import threading
import time
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request, Response
from fastapi.responses import StreamingResponse

from dulwich import porcelain
from dulwich.repo import Repo
from dulwich.server import DictBackend
from dulwich.web import make_wsgi_chain


def run_spike():
    with tempfile.TemporaryDirectory() as tmpdir:
        bare_path = os.path.join(tmpdir, "bare.git")
        work_path = os.path.join(tmpdir, "work")
        clone_path = os.path.join(tmpdir, "clone")

        # Init bare + working, commit, push
        os.makedirs(bare_path)
        os.makedirs(work_path)
        bare_repo = Repo.init_bare(bare_path)
        work_repo = Repo.init(work_path)
        readme = os.path.join(work_path, "README.md")
        Path(readme).write_text("# FastAPI+dulwich spike\n")
        porcelain.add(work_repo, paths=[readme])
        porcelain.commit(
            work_repo,
            message=b"Initial commit",
            author=b"Test User <test@example.com>",
            committer=b"Test User <test@example.com>",
        )
        porcelain.push(work_repo, bare_path, b"refs/heads/master:refs/heads/master")

        # Use a2wsgi to bridge dulwich WSGI → ASGI
        from a2wsgi import WSGIMiddleware

        backend = DictBackend({"/": bare_repo})
        dulwich_wsgi = make_wsgi_chain(backend)

        app = FastAPI()
        app.mount("/git", WSGIMiddleware(dulwich_wsgi))

        @app.get("/health")
        def health():
            return {"ok": True}

        import socket
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]

        config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error")
        server = uvicorn.Server(config)
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()

        for _ in range(30):
            try:
                import httpx
                r = httpx.get(f"http://127.0.0.1:{port}/health", timeout=1)
                if r.status_code == 200:
                    break
            except Exception:
                time.sleep(0.1)

        print(f"[spike] FastAPI+uvicorn running on port {port}")

        url = f"http://127.0.0.1:{port}/git/"
        print(f"[spike] Cloning from {url}")
        clone_repo = porcelain.clone(url, clone_path, checkout=True)
        print("[spike] Clone succeeded")

        cloned_readme = Path(clone_path) / "README.md"
        assert cloned_readme.exists(), "README.md missing"
        content = cloned_readme.read_text()
        assert "FastAPI+dulwich spike" in content
        print(f"[spike] Content verified: {content.strip()!r}")

        server.should_exit = True
        time.sleep(0.2)
        print("[spike] SUCCESS — a2wsgi + dulwich works.")
        return True


if __name__ == "__main__":
    try:
        ok = run_spike()
        sys.exit(0 if ok else 1)
    except Exception as e:
        print(f"[spike] FAILED: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
