"""
Per-marketplace git operations via dulwich (no git binary required).

Each marketplace has:
  data/marketplaces/<slug>/repo/     — bare git repo (serves smart-HTTP)
  data/marketplaces/<slug>/working/  — working tree used to stage + commit

The write pattern is always:
  write_files(...) → commit(...) → done
Never write to the working tree outside of write_files().
"""
import os
import posixpath
import shutil
import time
from pathlib import Path
from typing import Any

from dulwich import porcelain
from dulwich.index import commit_tree
from dulwich.objects import Blob, Commit, Tag, Tree
from dulwich.repo import Repo

from app.config import get_settings


def _marketplace_dir(slug: str) -> str:
    return os.path.join(get_settings().marketplaces_dir, slug)


def _repo_path(slug: str) -> str:
    return os.path.join(_marketplace_dir(slug), "repo")


def _work_path(slug: str) -> str:
    return os.path.join(_marketplace_dir(slug), "working")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def create_repo(slug: str) -> None:
    """Initialize a bare repo and working tree for a new marketplace."""
    repo_p = _repo_path(slug)
    work_p = _work_path(slug)
    os.makedirs(repo_p, exist_ok=False)
    os.makedirs(work_p, exist_ok=False)
    Repo.init_bare(repo_p)
    Repo.init(work_p)


def write_files(slug: str, files: dict[str, str | None]) -> None:
    """
    Write or delete files in the working tree.

    files: mapping of relative POSIX path → content string (or None to delete).
    Intermediate directories are created as needed.
    """
    work_p = _work_path(slug)
    for rel_path, content in files.items():
        abs_path = os.path.join(work_p, rel_path.replace("/", os.sep))
        if content is None:
            if os.path.exists(abs_path):
                os.remove(abs_path)
        else:
            os.makedirs(os.path.dirname(abs_path), exist_ok=True)
            Path(abs_path).write_text(content, encoding="utf-8")


def commit(
    slug: str,
    message: str,
    author_name: str,
    author_email: str,
) -> str:
    """
    Stage all working-tree changes and commit them to the bare repo.

    Returns the hex commit SHA.
    """
    work_p = _work_path(slug)
    repo_p = _repo_path(slug)
    work_repo = Repo(work_p)

    # Stage everything (add + remove)
    _stage_all(work_repo, work_p)

    # Write the tree from the index
    tree_id = work_repo.open_index().commit(work_repo.object_store)

    # Build a Commit object pointing to the tree
    author_bytes = f"{author_name} <{author_email}>".encode()
    now = int(time.time())
    c = Commit()
    c.tree = tree_id
    c.author = author_bytes
    c.committer = author_bytes
    c.author_time = now
    c.commit_time = now
    c.author_timezone = 0
    c.commit_timezone = 0
    c.encoding = b"UTF-8"
    c.message = message.encode()

    # Set parent if HEAD exists
    try:
        parent_sha = work_repo.refs[b"HEAD"]
        # HEAD might be a symref to an unborn branch (no commits yet)
        try:
            c.parents = [work_repo.refs[b"HEAD"]]
        except KeyError:
            c.parents = []
    except KeyError:
        c.parents = []

    work_repo.object_store.add_object(c)

    # Update the working-tree repo's branch ref
    branch_ref = _current_branch_ref(work_repo)
    work_repo.refs[branch_ref] = c.id

    # Push to the bare repo
    branch_name = branch_ref.decode().split("/")[-1]
    push_refspec = f"refs/heads/{branch_name}:refs/heads/{branch_name}".encode()
    porcelain.push(work_repo, repo_p, push_refspec)

    return c.id.decode()  # dulwich .id is already a 40-char hex bytes object


def delete_repo(slug: str) -> None:
    """Remove the entire marketplace directory (bare repo + working tree)."""
    mkt_dir = _marketplace_dir(slug)
    if os.path.exists(mkt_dir):
        shutil.rmtree(mkt_dir)


def reset_working_tree(slug: str) -> None:
    """
    Reset the working tree to match the latest commit in the bare repo.
    Called on write-path failures to undo partial filesystem changes.
    """
    repo_p = _repo_path(slug)
    work_p = _work_path(slug)
    bare = Repo(repo_p)

    try:
        head_ref = bare.refs[b"HEAD"]
    except KeyError:
        # No commits yet — just wipe non-.git files from working tree
        for item in os.listdir(work_p):
            if item != ".git":
                full = os.path.join(work_p, item)
                shutil.rmtree(full) if os.path.isdir(full) else os.remove(full)
        return

    # Checkout the HEAD commit into the working tree
    porcelain.checkout_branch(work_p, b"master")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _current_branch_ref(repo: Repo) -> bytes:
    """Return the ref that HEAD points to (e.g. b'refs/heads/master')."""
    symrefs = repo.refs.get_symrefs()
    return symrefs.get(b"HEAD", b"refs/heads/master")


def _stage_all(repo: Repo, work_path: str) -> None:
    """
    Stage all changes: new/modified files added, deleted files removed.
    """
    # Collect all real files (excluding .git)
    to_add = []
    for dirpath, dirnames, filenames in os.walk(work_path):
        dirnames[:] = [d for d in dirnames if d != ".git"]
        for fname in filenames:
            abs_path = os.path.join(dirpath, fname)
            rel = os.path.relpath(abs_path, work_path)
            to_add.append(rel)

    # Stage new/modified files
    if to_add:
        porcelain.add(repo, paths=[os.path.join(work_path, p) for p in to_add])

    # Remove files that are tracked but no longer on disk
    tracked = set(repo.open_index())
    on_disk = {p.encode() for p in to_add}
    # Convert OS paths to POSIX bytes for index comparison
    on_disk_posix = set()
    for p in to_add:
        on_disk_posix.add(p.replace(os.sep, "/").encode())

    idx = repo.open_index()
    for key in list(idx):
        key_posix = key.replace(b"\\", b"/")
        if key_posix not in on_disk_posix:
            del idx[key]
    idx.write()
