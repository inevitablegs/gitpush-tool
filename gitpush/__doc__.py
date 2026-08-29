"""
GitPush Tool - Supercharged Git CLI (v0.4.0)

A powerful command-line tool that simplifies Git operations with automatic GitHub
repository creation, pre-push diffstat inspection, and dangerous operation safeguards.

Key Features:
• Pre-push diffstat line changes (+/-) and branch sync inspection
• Dangerous operation guard (reset --hard, force push, branch delete, clean, dirty rebase)
• Protected branch & detached HEAD detection
• One-command GitHub repo creation
• Automatic Git initialization
• Safe force pushing (--force-with-lease)
• GitHub CLI integration

Basic Usage:
  gitpush "Commit message"              # Standard push with preview
  gitpush "Commit message" -y           # Push without confirmation prompt
  gitpush --dry-run                     # Preview changes without pushing
  gitpush guard git reset --hard HEAD~5 # Guard dangerous Git commands
  gitpush --new-repo project-name       # Create new repo
  gitpush --force                       # Safe force push

Documentation: https://github.com/inevitablegs/gitpush
Issues: https://github.com/inevitablegs/gitpush/issues
"""