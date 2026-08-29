import unittest
import os
import sys
import tempfile
import shutil
import subprocess
from pathlib import Path

# Add package root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from gitpush.undo import (
    get_commit_info,
    is_commit_pushed,
    get_recent_git_actions,
    undo_commit,
    format_recent_actions_menu
)


class TestUndoEngine(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        subprocess.run(["git", "init"], cwd=self.test_dir, capture_output=True, check=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=self.test_dir, capture_output=True, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=self.test_dir, capture_output=True, check=True)
        subprocess.run(["git", "branch", "-M", "main"], cwd=self.test_dir, capture_output=True, check=True)
        
        # Commit 1
        with open(os.path.join(self.test_dir, "file1.txt"), "w") as f:
            f.write("commit 1\n")
        subprocess.run(["git", "add", "."], cwd=self.test_dir, check=True)
        subprocess.run(["git", "commit", "-m", "First commit"], cwd=self.test_dir, check=True)

        # Commit 2
        with open(os.path.join(self.test_dir, "file2.txt"), "w") as f:
            f.write("commit 2\n")
        subprocess.run(["git", "add", "."], cwd=self.test_dir, check=True)
        subprocess.run(["git", "commit", "-m", "Second commit: Add payment API"], cwd=self.test_dir, check=True)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_get_commit_info(self):
        info = get_commit_info("HEAD", cwd=self.test_dir)
        self.assertIsNotNone(info)
        self.assertIn("Add payment API", info["subject"])
        self.assertFalse(info["is_merge"])

    def test_get_recent_actions(self):
        actions = get_recent_git_actions(count=5, cwd=self.test_dir)
        self.assertEqual(len(actions), 2)
        self.assertIn("Add payment API", actions[0]["subject"])
        self.assertIn("First commit", actions[1]["subject"])

    def test_format_recent_actions_menu(self):
        actions = get_recent_git_actions(count=5, cwd=self.test_dir)
        menu = format_recent_actions_menu(actions)
        self.assertIn("Recent Git actions", menu)
        self.assertIn("Add payment API", menu)

    def test_undo_commit_soft(self):
        # We have 2 commits. Undoing HEAD should rewind to First commit,
        # but file2.txt changes must be kept in the worktree!
        self.assertTrue(os.path.exists(os.path.join(self.test_dir, "file2.txt")))

        success = undo_commit(auto_confirm=True, cwd=self.test_dir)
        self.assertTrue(success)

        # Verify HEAD is now on "First commit"
        info = get_commit_info("HEAD", cwd=self.test_dir)
        self.assertEqual(info["subject"], "First commit")

        # Verify file2.txt still exists in working directory!
        self.assertTrue(os.path.exists(os.path.join(self.test_dir, "file2.txt")))


if __name__ == "__main__":
    unittest.main()
