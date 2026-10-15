"""Exercise real Git safeguards in disposable repos; never call an AI provider."""

import contextlib
import io
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1]


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="rakathon-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "repo with spaces"
        self.root.mkdir()
        self.environment = dict(
            os.environ,
            GIT_CONFIG_NOSYSTEM="1",
            GIT_CONFIG_GLOBAL=os.devnull,
            GIT_TERMINAL_PROMPT="0",
        )
        # Isolate Git from inherited repository selectors and inline configs.
        for name in list(self.environment):
            if name.startswith("GIT_") and name not in {
                "GIT_CONFIG_NOSYSTEM", "GIT_CONFIG_GLOBAL", "GIT_TERMINAL_PROMPT"
            }:
                del self.environment[name]
        self.environ_patch = patch.dict(os.environ, self.environment, clear=True)
        self.environ_patch.start()
        self.addCleanup(self.environ_patch.stop)
        self.git("init", "-b", "main")
        shutil.copy2(SOURCE / "rak", self.root / "rak")
        (self.root / ".gitignore").write_text("/.worktrees/\n")
        self.cli = runpy.run_path(str(self.root / "rak"))

    def git(self, *args, cwd=None, check=True):
        return subprocess.run(
            ["git", "-c", "core.hooksPath=/dev/null", "-c", "commit.gpgsign=false",
             "-c", "user.name=Workspace Test", "-c", "user.email=test@example.invalid", *args],
            cwd=cwd or self.root, check=check, text=True, capture_output=True,
        )

    def commit(self):
        self.git("add", "rak", ".gitignore")
        self.git("commit", "-m", "chore: test baseline")

    def invoke(self, *args):
        return subprocess.run(
            [sys.executable, str(self.root / "rak"), *args],
            cwd=self.root, text=True, capture_output=True,
        ).returncode

    def test_initial_commit_required(self):
        self.assertEqual(self.invoke("task", "example"), 1)
        self.assertFalse((self.root / ".worktrees").exists())

    def test_invalid_slugs_cannot_escape(self):
        for slug in ["../escape", "/tmp/escape", "BadName", "a/b", "--force", "a" * 61]:
            with self.subTest(slug=slug):
                # Test validation directly so argparse doesn't interpret --force.
                with self.assertRaises(ValueError):
                    self.cli["new_task"](slug)

    def test_dirty_checkout_refused(self):
        self.commit()
        (self.root / "keep.txt").write_text("preserve\n")
        self.assertEqual(self.invoke("task", "example"), 1)
        self.assertEqual((self.root / "keep.txt").read_text(), "preserve\n")
        self.assertFalse((self.root / ".worktrees").exists())

    def test_create_and_duplicate_preserve_work(self):
        self.commit()
        self.assertEqual(self.invoke("task", "example"), 0)
        worktree = self.root / ".worktrees/example"
        self.assertEqual(self.git("branch", "--show-current", cwd=worktree).stdout.strip(), "task/example")
        (worktree / "keep.txt").write_text("work in progress\n")
        self.assertEqual(self.invoke("task", "example"), 1)
        self.assertEqual((worktree / "keep.txt").read_text(), "work in progress\n")
        self.assertNotEqual(self.git("worktree", "remove", str(worktree), check=False).returncode, 0)

    def test_existing_branch_refused(self):
        self.commit()
        self.git("branch", "task/example")
        self.assertNotEqual(self.invoke("task", "example"), 0)
        self.assertFalse((self.root / ".worktrees/example").exists())
        self.git("show-ref", "--verify", "refs/heads/task/example")

    def test_ignored_parent_required(self):
        (self.root / ".gitignore").write_text("# intentionally missing ignore\n")
        self.commit()
        self.assertEqual(self.invoke("task", "example"), 1)
        self.assertFalse((self.root / ".worktrees").exists())

    def test_symlink_parent_refused(self):
        self.commit()
        external = Path(self.temporary.name) / "external"
        external.mkdir()
        (self.root / ".worktrees").symlink_to(external, target_is_directory=True)
        self.assertEqual(self.invoke("task", "example"), 1)
        self.assertEqual(list(external.iterdir()), [])

    def test_nested_task_creation_refused(self):
        self.commit()
        self.assertEqual(self.invoke("task", "example"), 0)
        nested = runpy.run_path(str(self.root / ".worktrees/example/rak"))
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(nested["main"](["task", "nested"]), 1)
        self.assertFalse((self.root / ".worktrees/example/.worktrees").exists())

    def test_agent_refuses_main(self):
        self.commit()
        with patch("os.execvp") as execute, contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(self.cli["main"](["agent", "codex"]), 1)
            execute.assert_not_called()

    def test_missing_editor_does_not_create_partial_task(self):
        self.commit()
        with patch("shutil.which", return_value=None), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(self.cli["main"](["task", "example", "--open"]), 1)
        self.assertFalse((self.root / ".worktrees").exists())

    def test_missing_agent_does_not_launch_anything(self):
        self.commit()
        self.assertEqual(self.invoke("task", "example"), 0)
        nested = runpy.run_path(str(self.root / ".worktrees/example/rak"))
        with patch("shutil.which", return_value=None), patch("os.execvp") as execute, \
                contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(nested["main"](["agent", "agy"]), 1)
            execute.assert_not_called()

    def test_agent_launches_only_selected_tool_in_task_checkout(self):
        self.commit()
        self.assertEqual(self.invoke("task", "example"), 0)
        worktree = self.root / ".worktrees/example"
        nested = runpy.run_path(str(worktree / "rak"))
        with patch("shutil.which", return_value="/test/agy"), patch("os.execvp") as execute, \
                patch("os.chdir") as change, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(nested["main"](["agent", "agy"]), 0)
            change.assert_called_once_with(worktree)
            execute.assert_called_once_with("agy", ["agy"])


if __name__ == "__main__":
    unittest.main()
