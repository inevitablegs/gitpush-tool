import unittest
import sys
import subprocess
from pathlib import Path

# Add package root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from gitpush.cli import handle_guard_command


class TestCLI(unittest.TestCase):

    def test_guard_help_when_no_args(self):
        code = handle_guard_command([])
        self.assertEqual(code, 1)

    def test_guard_dry_check(self):
        # Run git status through guard with -y
        code = handle_guard_command(["status"], auto_confirm=True)
        self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
