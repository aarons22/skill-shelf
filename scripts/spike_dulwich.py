"""
Dulwich smart-HTTP spike.

Tests:
1. Init a bare repo with dulwich.
2. Add a file via dulwich (porcelain.commit / repo.do_commit).
3. Stand up a minimal WSGI smart-HTTP server using dulwich.web.
4. Clone it with dulwich.porcelain.clone into a temp dir.
5. Assert the file appears in the clone.

Exit 0 on success, non-zero on failure.
"""
import os
import sys
import tempfile
import threading
import time
from pathlib import Path
from wsgiref.simple_server import WSGIRequestHandler, make_server

from dulwich import porcelain
from dulwich.repo import Repo
from dulwich.server import DictBackend
from dulwich.web import HTTPGitApplication, make_wsgi_chain


def _silent_handler(*args, **kwargs):
    pass


class QuietHandler(WSGIRequestHandler):
    def log_message(self, *args):
        pass


def run_spike():
    with tempfile.TemporaryDirectory() as tmpdir:
        bare_path = os.path.join(tmpdir, "bare.git")
        clone_path = os.path.join(tmpdir, "clone")
        work_path = os.path.join(tmpdir, "work")

        # --- Step 1: Init bare repo ---
        os.makedirs(bare_path)
        bare_repo = Repo.init_bare(bare_path)

        # --- Step 2: Create an initial commit via a working tree ---
        # dulwich doesn't write to bare repos directly from porcelain.
        # Pattern: init a working tree, make a commit, then push to bare.
        os.makedirs(work_path)
        work_repo = Repo.init(work_path)
        readme = os.path.join(work_path, "README.md")
        Path(readme).write_text("# Hello from spike\n")
        porcelain.add(work_repo, paths=[readme])
        porcelain.commit(
            work_repo,
            message=b"Initial commit",
            author=b"Test User <test@example.com>",
            committer=b"Test User <test@example.com>",
        )
        # Push to bare — dulwich defaults to 'master', not 'main'
        porcelain.push(work_repo, bare_path, b"refs/heads/master:refs/heads/master")

        print(f"[spike] Bare repo created at {bare_path}")
        print(f"[spike] Initial commit pushed")

        # --- Step 3: Serve the bare repo over smart-HTTP ---
        # DictBackend maps a path prefix to a Repo
        backend = DictBackend({"/": bare_repo})
        wsgi_app = make_wsgi_chain(backend)

        server = make_server("127.0.0.1", 0, wsgi_app, handler_class=QuietHandler)
        port = server.server_address[1]
        print(f"[spike] Serving on http://127.0.0.1:{port}/")

        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        time.sleep(0.1)

        # --- Step 4: Clone via dulwich ---
        url = f"http://127.0.0.1:{port}/"
        print(f"[spike] Cloning from {url} ...")
        clone_repo = porcelain.clone(url, clone_path, checkout=True)
        print(f"[spike] Clone succeeded")

        # --- Step 5: Assert file exists ---
        cloned_readme = Path(clone_path) / "README.md"
        assert cloned_readme.exists(), f"README.md missing in clone at {clone_path}"
        content = cloned_readme.read_text()
        assert "Hello from spike" in content, f"Unexpected content: {content!r}"
        print(f"[spike] File content verified: {content.strip()!r}")

        server.shutdown()
        print("[spike] SUCCESS — dulwich smart-HTTP serve+clone works.")
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
