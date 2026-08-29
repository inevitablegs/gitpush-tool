import unittest
import os
import sys
import tempfile
import shutil
import subprocess
from pathlib import Path

# Add package root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from gitpush.safety import (
    is_git_repo,
    get_repo_name,
    get_repo_root,
    get_current_branch,
    is_detached_head,
    is_protected_branch,
    get_ahead_behind,
    get_diffstat_summary,
    DangerousOperationAnalyzer,
    format_danger_box,
    format_prepush_summary
)


class TestSafetyEngine(unittest.TestCase):

    def setUp(self):
        # Create a temporary directory and initialize a git repo for testing
        self.test_dir = tempfile.mkdtemp()
        subprocess.run(["git", "init"], cwd=self.test_dir, capture_output=True, check=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=self.test_dir, capture_output=True, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=self.test_dir, capture_output=True, check=True)
        subprocess.run(["git", "branch", "-M", "main"], cwd=self.test_dir, capture_output=True, check=True)
        # Create initial root commit
        init_file = os.path.join(self.test_dir, "init.txt")
        with open(init_file, "w") as f:
            f.write("init\n")
        subprocess.run(["git", "add", "."], cwd=self.test_dir, capture_output=True, check=True)
        subprocess.run(["git", "commit", "-m", "initial commit"], cwd=self.test_dir, capture_output=True, check=True)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_is_git_repo(self):
        self.assertTrue(is_git_repo(cwd=self.test_dir))
        non_repo = tempfile.mkdtemp()
        try:
            self.assertFalse(is_git_repo(cwd=non_repo))
        finally:
            shutil.rmtree(non_repo, ignore_errors=True)

    def test_repo_name_and_root(self):
        root = get_repo_root(cwd=self.test_dir)
        self.assertIsNotNone(root)
        self.assertEqual(os.path.abspath(root), os.path.abspath(self.test_dir))
        name = get_repo_name(cwd=self.test_dir)
        self.assertEqual(name, os.path.basename(self.test_dir))

    def test_protected_branch_detection(self):
        self.assertTrue(is_protected_branch("main"))
        self.assertTrue(is_protected_branch("master"))
        self.assertTrue(is_protected_branch("prod"))
        self.assertTrue(is_protected_branch("production"))
        self.assertTrue(is_protected_branch("release"))
        self.assertTrue(is_protected_branch("dev"))
        self.assertFalse(is_protected_branch("feature/login"))
        self.assertFalse(is_protected_branch("bugfix-123"))

    def test_diffstat_summary(self):
        # Initially clean
        diff = get_diffstat_summary(cwd=self.test_dir)
        self.assertFalse(diff["has_changes"])

        # Create a file
        f1 = os.path.join(self.test_dir, "hello.txt")
        with open(f1, "w") as f:
            f.write("Line 1\nLine 2\nLine 3\n")

        diff = get_diffstat_summary(cwd=self.test_dir)
        self.assertTrue(diff["has_changes"])
        self.assertEqual(diff["untracked_count"], 1)
        self.assertEqual(diff["total_additions"], 3)

        # Commit initial file
        subprocess.run(["git", "add", "."], cwd=self.test_dir, check=True)
        subprocess.run(["git", "commit", "-m", "Init"], cwd=self.test_dir, check=True)

        # Modify file
        with open(f1, "w") as f:
            f.write("Line 1 modified\nLine 2\nLine 3\nLine 4 added\n")

        diff = get_diffstat_summary(cwd=self.test_dir)
        self.assertTrue(diff["has_changes"])
        self.assertEqual(diff["modified_count"], 1)
        self.assertTrue(diff["total_additions"] > 0)

    def test_reset_hard_analysis(self):
        # Create 3 commits
        f = os.path.join(self.test_dir, "file.txt")
        for i in range(1, 4):
            with open(f, "a") as fp:
                fp.write(f"commit {i}\n")
            subprocess.run(["git", "add", "."], cwd=self.test_dir, check=True)
            subprocess.run(["git", "commit", "-m", f"commit {i}"], cwd=self.test_dir, check=True)

        # Make uncommitted changes
        with open(f, "a") as fp:
            fp.write("uncommitted work\n")

        report = DangerousOperationAnalyzer.analyze_reset_hard("HEAD~2", cwd=self.test_dir)
        self.assertTrue(report.is_dangerous)
        self.assertEqual(report.lost_items.get("commits"), 2)
        self.assertEqual(report.lost_items.get("modified_files"), 1)

        # Format danger box output
        box = format_danger_box(report, repo_name="test-repo")
        self.assertIn("git reset --hard HEAD~2", box)
        self.assertIn("2 commit(s)", box)
        self.assertIn("1 modified/staged file(s)", box)
        self.assertIn("test-repo", box)

    def test_force_push_analysis(self):
        report = DangerousOperationAnalyzer.analyze_force_push("origin", "main", cwd=self.test_dir)
        self.assertTrue(report.is_dangerous)
        self.assertIn("PROTECTED BRANCH", report.risks[0])

    def test_clean_analysis(self):
        # Create untracked file
        untracked = os.path.join(self.test_dir, "untracked.txt")
        with open(untracked, "w") as fp:
            fp.write("untracked\n")

        report = DangerousOperationAnalyzer.analyze_clean(force=True, remove_dirs=True, cwd=self.test_dir)
        self.assertTrue(report.is_dangerous)
        self.assertEqual(report.lost_items.get("untracked_files"), 1)

    def test_branch_delete_analysis(self):
        # Create a branch with an unmerged commit
        subprocess.run(["git", "checkout", "-b", "feature-x"], cwd=self.test_dir, check=True)
        f = os.path.join(self.test_dir, "feat.txt")
        with open(f, "w") as fp:
            fp.write("feature\n")
        subprocess.run(["git", "add", "."], cwd=self.test_dir, check=True)
        subprocess.run(["git", "commit", "-m", "feature commit"], cwd=self.test_dir, check=True)
        subprocess.run(["git", "checkout", "main"], cwd=self.test_dir, check=True)

        report = DangerousOperationAnalyzer.analyze_branch_delete("feature-x", force=True, cwd=self.test_dir)
        self.assertTrue(report.is_dangerous)
        self.assertEqual(report.lost_items.get("unmerged_commits"), 1)

    def test_arbitrary_command_analyzer(self):
        # Test command parsing
        rep1 = DangerousOperationAnalyzer.analyze_arbitrary_command(["git", "reset", "--hard", "HEAD~3"], cwd=self.test_dir)
        self.assertIsNotNone(rep1)
        self.assertIn("reset --hard", rep1.operation_name)

        rep2 = DangerousOperationAnalyzer.analyze_arbitrary_command(["git", "clean", "-fd"], cwd=self.test_dir)
        self.assertIsNotNone(rep2)
        self.assertIn("Clean", rep2.operation_name)

        rep3 = DangerousOperationAnalyzer.analyze_arbitrary_command(["git", "push", "--force", "origin", "main"], cwd=self.test_dir)
        self.assertIsNotNone(rep3)
        self.assertIn("Force Push", rep3.operation_name)


if __name__ == "__main__":
    unittest.main()
