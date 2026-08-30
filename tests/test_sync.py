import unittest
import os
import sys
import tempfile
import shutil
import subprocess
from pathlib import Path

# Add package root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from gitpush.sync import (
    _auto_generate_message,
    _stage_and_commit,
    _get_tracking_info,
    _has_remote,
    run_sync_flow
)
from gitpush.safety import FileChangeStat, get_diffstat_summary


class TestSyncEngine(unittest.TestCase):

    def setUp(self):
        # Create bare remote repository
        self.remote_dir = tempfile.mkdtemp()
        subprocess.run(["git", "init", "--bare"], cwd=self.remote_dir, capture_output=True, check=True)

        # Create local clone / repo
        self.local_dir = tempfile.mkdtemp()
        subprocess.run(["git", "init"], cwd=self.local_dir, capture_output=True, check=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=self.local_dir, capture_output=True, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=self.local_dir, capture_output=True, check=True)
        subprocess.run(["git", "branch", "-M", "main"], cwd=self.local_dir, capture_output=True, check=True)
        subprocess.run(["git", "remote", "add", "origin", self.remote_dir], cwd=self.local_dir, capture_output=True, check=True)

        # Initial commit & push to set up origin/main
        file1 = os.path.join(self.local_dir, "initial.txt")
        with open(file1, "w") as f:
            f.write("initial\n")
        subprocess.run(["git", "add", "."], cwd=self.local_dir, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=self.local_dir, check=True, capture_output=True)
        subprocess.run(["git", "push", "-u", "origin", "main"], cwd=self.local_dir, check=True, capture_output=True)

    def tearDown(self):
        shutil.rmtree(self.remote_dir, ignore_errors=True)
        shutil.rmtree(self.local_dir, ignore_errors=True)

    def test_auto_generate_message(self):
        mock_diff = {
            "modified_count": 1,
            "total_additions": 5,
            "total_deletions": 2,
            "files": [FileChangeStat("foo.py", "M", 5, 2)]
        }
        msg = _auto_generate_message(mock_diff)
        self.assertEqual(msg, "Update foo.py (+5, -2)")

        mock_diff_multi = {
            "modified_count": 3,
            "total_additions": 10,
            "total_deletions": 4,
            "files": [
                FileChangeStat("a.py", "M", 5, 2),
                FileChangeStat("b.py", "A", 5, 0),
                FileChangeStat("c.py", "D", 0, 2)
            ]
        }
        msg_multi = _auto_generate_message(mock_diff_multi)
        self.assertEqual(msg_multi, "Update 3 files (+10, -4)")

    def test_stage_and_commit(self):
        new_file = os.path.join(self.local_dir, "new_file.txt")
        with open(new_file, "w") as f:
            f.write("hello world\n")

        success = _stage_and_commit("Test commit", cwd=self.local_dir)
        self.assertTrue(success)

        # Verify status is clean
        diff = get_diffstat_summary(cwd=self.local_dir)
        self.assertFalse(diff["has_changes"])

    def test_sync_already_synced(self):
        # Local and remote are currently identical
        ret = run_sync_flow(auto_confirm=True, cwd=self.local_dir)
        self.assertEqual(ret, 0)

    def test_sync_scenario_a_local_ahead(self):
        # Scenario A: Local commits ahead, remote has 0 new commits -> Safe to push
        new_file = os.path.join(self.local_dir, "feature.txt")
        with open(new_file, "w") as f:
            f.write("feature commit\n")
        subprocess.run(["git", "add", "."], cwd=self.local_dir, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Add feature"], cwd=self.local_dir, check=True, capture_output=True)

        ret = run_sync_flow(auto_confirm=True, cwd=self.local_dir)
        self.assertEqual(ret, 0)

        # Check that remote now has the commit
        res = subprocess.run(["git", "rev-list", "--count", "origin/main...main"], cwd=self.local_dir, capture_output=True, text=True)
        self.assertEqual(res.stdout.strip(), "0")

    def test_sync_scenario_c_dirty_tree(self):
        # Scenario C: Modified files detected -> auto-commits and pushes
        new_file = os.path.join(self.local_dir, "dirty.txt")
        with open(new_file, "w") as f:
            f.write("dirty worktree\n")

        ret = run_sync_flow(auto_confirm=True, commit_message="Auto committed dirty file", cwd=self.local_dir)
        self.assertEqual(ret, 0)

        # Check that worktree is clean and pushed
        diff = get_diffstat_summary(cwd=self.local_dir)
        self.assertFalse(diff["has_changes"])

        res = subprocess.run(["git", "rev-list", "--count", "origin/main...main"], cwd=self.local_dir, capture_output=True, text=True)
        self.assertEqual(res.stdout.strip(), "0")

    def test_sync_scenario_b_diverged_rebase(self):
        # Scenario B: Local is ahead, and remote has new commits -> diverged
        # Create a second local clone to make commits and push to remote
        second_local = tempfile.mkdtemp()
        try:
            subprocess.run(["git", "clone", "-b", "main", self.remote_dir, second_local], capture_output=True, check=True)
            subprocess.run(["git", "config", "user.name", "Teammate"], cwd=second_local, capture_output=True, check=True)
            subprocess.run(["git", "config", "user.email", "teammate@example.com"], cwd=second_local, capture_output=True, check=True)
            
            with open(os.path.join(second_local, "remote_work.txt"), "w") as f:
                f.write("remote work\n")
            subprocess.run(["git", "add", "."], cwd=second_local, check=True, capture_output=True)
            subprocess.run(["git", "commit", "-m", "Remote teammate commit"], cwd=second_local, check=True, capture_output=True)
            subprocess.run(["git", "push", "origin", "main"], cwd=second_local, check=True, capture_output=True)

            # Local has its own distinct commit
            with open(os.path.join(self.local_dir, "local_work.txt"), "w") as f:
                f.write("local work\n")
            subprocess.run(["git", "add", "."], cwd=self.local_dir, check=True, capture_output=True)
            subprocess.run(["git", "commit", "-m", "Local commit"], cwd=self.local_dir, check=True, capture_output=True)

            # Run sync with prefer_rebase=True
            ret = run_sync_flow(auto_confirm=True, prefer_rebase=True, cwd=self.local_dir)
            self.assertEqual(ret, 0)

            # Both files should exist in local_dir
            self.assertTrue(os.path.exists(os.path.join(self.local_dir, "remote_work.txt")))
            self.assertTrue(os.path.exists(os.path.join(self.local_dir, "local_work.txt")))
        finally:
            shutil.rmtree(second_local, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
