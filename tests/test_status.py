import unittest
import os
import sys
import tempfile
import shutil
import subprocess
from pathlib import Path

# Add package root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from gitpush.status import (
    get_tracking_branch,
    get_stash_count,
    get_worktree_breakdown,
    calculate_repo_health,
    get_decision_recommendations,
    format_status_dashboard
)


class TestStatusDashboard(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        subprocess.run(["git", "init"], cwd=self.test_dir, capture_output=True, check=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=self.test_dir, capture_output=True, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=self.test_dir, capture_output=True, check=True)
        subprocess.run(["git", "branch", "-M", "feature/payment"], cwd=self.test_dir, capture_output=True, check=True)
        
        # Initial commit
        init_file = os.path.join(self.test_dir, "init.txt")
        with open(init_file, "w") as f:
            f.write("init\n")
        subprocess.run(["git", "add", "."], cwd=self.test_dir, capture_output=True, check=True)
        subprocess.run(["git", "commit", "-m", "initial commit"], cwd=self.test_dir, capture_output=True, check=True)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_worktree_breakdown(self):
        # Create modified, added, untracked, deleted files
        f1 = os.path.join(self.test_dir, "init.txt")
        with open(f1, "w") as f:
            f.write("init modified\n")

        f2 = os.path.join(self.test_dir, "new_staged.txt")
        with open(f2, "w") as f:
            f.write("staged\n")
        subprocess.run(["git", "add", "new_staged.txt"], cwd=self.test_dir, check=True)

        f3 = os.path.join(self.test_dir, "untracked.txt")
        with open(f3, "w") as f:
            f.write("untracked\n")

        counts = get_worktree_breakdown(cwd=self.test_dir)
        self.assertEqual(counts["modified"], 1)
        self.assertEqual(counts["added"], 1)
        self.assertEqual(counts["untracked"], 1)

    def test_health_calculation(self):
        score_clean, label_clean, _ = calculate_repo_health(
            detached=False,
            unmerged_count=0,
            behind_count=0,
            diverged=False,
            modified_count=0,
            untracked_count=0,
            stash_count=0,
            is_protected=False
        )
        self.assertEqual(score_clean, 100)
        self.assertIn("Excellent", label_clean)

        score_dirty, label_dirty, _ = calculate_repo_health(
            detached=True,
            unmerged_count=1,
            behind_count=3,
            diverged=True,
            modified_count=6,
            untracked_count=6,
            stash_count=6,
            is_protected=True
        )
        self.assertTrue(score_dirty < 50)

    def test_decision_recommendations(self):
        # Test behind remote recommendation
        notes, recs = get_decision_recommendations(
            branch="feature/payment",
            tracking="origin/feature/payment",
            ahead=0,
            behind=2,
            diverged=False,
            detached=False,
            worktree={"modified": 0, "added": 0, "deleted": 0, "untracked": 0, "renamed": 0, "unmerged": 0},
            is_protected=False
        )
        self.assertTrue(any("git pull --rebase" in r for r in recs))
        self.assertTrue(any("Remote has" in n for n in notes))

    def test_format_status_dashboard(self):
        dashboard = format_status_dashboard(cwd=self.test_dir)
        self.assertIn("Repository:", dashboard)
        self.assertIn("feature/payment", dashboard)
        self.assertIn("WORKTREE", dashboard)
        self.assertIn("COMMITS", dashboard)
        self.assertIn("Health:", dashboard)
        self.assertIn("Recommended:", dashboard)


if __name__ == "__main__":
    unittest.main()
