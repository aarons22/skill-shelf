"""Unit tests for git_store.py — all against temp directories, no git binary."""
import os
import subprocess
import time

import pytest
from dulwich import porcelain
from dulwich.repo import Repo

from app.lib import git_store


@pytest.fixture
def tmp_data_dir(tmp_path, monkeypatch):
    """Point SKILLSHELF_DATA_DIR at a temp directory."""
    data_dir = str(tmp_path / "data")
    monkeypatch.setenv("SKILLSHELF_DATA_DIR", data_dir)
    from app import config as cfg
    cfg.get_settings.cache_clear()
    os.makedirs(os.path.join(data_dir, "marketplaces"), exist_ok=True)
    yield data_dir
    cfg.get_settings.cache_clear()


def test_create_repo_creates_dirs(tmp_data_dir):
    git_store.create_repo("test-mkt")
    assert os.path.isdir(git_store._repo_path("test-mkt"))
    assert os.path.isdir(git_store._work_path("test-mkt"))
    # Bare repo should have a HEAD file
    assert os.path.exists(os.path.join(git_store._repo_path("test-mkt"), "HEAD"))


def test_create_repo_idempotent_fails_on_duplicate(tmp_data_dir):
    git_store.create_repo("dup-mkt")
    with pytest.raises(Exception):
        git_store.create_repo("dup-mkt")


def test_write_files_creates_and_deletes(tmp_data_dir):
    git_store.create_repo("write-test")
    git_store.write_files("write-test", {
        "README.md": "# Hello",
        ".claude-plugin/marketplace.json": '{"name":"test"}',
    })
    work_p = git_store._work_path("write-test")
    assert (os.path.join(work_p, "README.md"))
    assert os.path.exists(os.path.join(work_p, ".claude-plugin", "marketplace.json"))

    # Delete one file
    git_store.write_files("write-test", {"README.md": None})
    assert not os.path.exists(os.path.join(work_p, "README.md"))
    assert os.path.exists(os.path.join(work_p, ".claude-plugin", "marketplace.json"))


def test_commit_creates_commits_in_bare_repo(tmp_data_dir):
    git_store.create_repo("commit-test")
    git_store.write_files("commit-test", {
        ".claude-plugin/marketplace.json": '{"name":"commit-test","plugins":[]}',
    })
    sha = git_store.commit("commit-test", "Initial commit", "Test User", "test@example.com")
    assert len(sha) == 40

    # Bare repo should have a commit
    bare = Repo(git_store._repo_path("commit-test"))
    assert bare.refs[b"HEAD"] is not None or b"refs/heads/master" in bare.refs


def test_commit_full_skill_layout(tmp_data_dir):
    """Assert the §6 on-disk layout is committed correctly."""
    slug = "layout-test"
    skill_slug = "quarterly-report"
    git_store.create_repo(slug)

    files = {
        ".claude-plugin/marketplace.json": '{"name":"layout-test","plugins":[]}',
        ".agents/plugins/marketplace.json": '{"name":"layout-test","plugins":[]}',
        f"plugins/{skill_slug}/.claude-plugin/plugin.json": '{"name":"quarterly-report"}',
        f"plugins/{skill_slug}/.codex-plugin/plugin.json": '{"name":"quarterly-report"}',
        f"plugins/{skill_slug}/skills/{skill_slug}/SKILL.md": (
            "---\nname: quarterly-report\ndescription: test\n---\nDo stuff\n"
        ),
    }
    git_store.write_files(slug, files)
    sha = git_store.commit(slug, "Add skill", "Test", "test@example.com")
    assert len(sha) == 40

    # Clone the bare repo and check files exist
    import tempfile
    with tempfile.TemporaryDirectory() as clone_dir:
        cloned = porcelain.clone(git_store._repo_path(slug), clone_dir, checkout=True)
        assert os.path.exists(os.path.join(clone_dir, ".claude-plugin", "marketplace.json"))
        assert os.path.exists(os.path.join(clone_dir, ".agents", "plugins", "marketplace.json"))
        assert os.path.exists(os.path.join(clone_dir, "plugins", skill_slug, ".claude-plugin", "plugin.json"))
        assert os.path.exists(os.path.join(clone_dir, "plugins", skill_slug, ".codex-plugin", "plugin.json"))
        skill_md = os.path.join(clone_dir, "plugins", skill_slug, "skills", skill_slug, "SKILL.md")
        assert os.path.exists(skill_md)
        content = open(skill_md).read()
        assert "quarterly-report" in content


def test_delete_repo(tmp_data_dir):
    git_store.create_repo("del-test")
    assert os.path.isdir(git_store._marketplace_dir("del-test"))
    git_store.delete_repo("del-test")
    assert not os.path.exists(git_store._marketplace_dir("del-test"))


def test_no_git_binary_used(tmp_data_dir, monkeypatch):
    """Confirm git_store never calls a git binary (no subprocess to git)."""
    original_popen = subprocess.Popen

    def assert_no_git(args, *a, **kw):
        if isinstance(args, (list, tuple)) and args and str(args[0]).endswith("git"):
            raise AssertionError(f"git binary invoked: {args}")
        return original_popen(args, *a, **kw)

    monkeypatch.setattr(subprocess, "Popen", assert_no_git)
    git_store.create_repo("no-git-test")
    git_store.write_files("no-git-test", {"README.md": "hello"})
    git_store.commit("no-git-test", "test", "T", "t@t.com")
