# GitPush Tool 🚀

[![PyPI version](https://img.shields.io/pypi/v/gitpush-tool.svg)](https://pypi.org/project/gitpush-tool/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

A supercharged Git CLI and safety tool that simplifies repository creation and pushing with intelligent defaults, rich pre-push diffstat inspection (`+++---` lines), and active safeguards against dangerous Git commands.

---

## ✨ Features

- **Pre-Push Safety & Diffstat Preview:** See changed files, line additions/deletions (`+X, -Y`), ahead/behind status, and pending commits before pushing.
- **Dangerous Git Operation Guard:** Analyzes and protects against risky actions (`reset --hard`, force pushes, deleting unmerged branches, dirty `git clean`, detached HEADs).
- **Protected Branch Safeguard:** Automatically detects and alerts when pushing or force-pushing to `main`, `master`, `prod`, `release`, or `dev`.
- **One-Command GitHub Repo Creation:** Initialize Git, create a remote GitHub repo, and push in a single step via GitHub CLI (`gh`).
- **Safe Force Pushing:** Uses `--force-with-lease` by default to avoid overwriting teammate commits.
- **Dry-Run Mode:** Preview your push inspection without modifying anything.
- **Non-Interactive & CI Friendly:** Skip prompts with `-y` or `--yes`.

---

## 📦 Installation

```bash
pip install gitpush-tool
```

---

## 🛡️ Pre-Push Warning & Inspection

Whenever you run `gitpush`, you get an instant, clear breakdown of your repository state:

```text
═══════════════════════════════════════════════════════════════
 🚀 GITPUSH PRE-PUSH INSPECTION & SUMMARY
═══════════════════════════════════════════════════════════════

Repository:    my-project (/Users/username/Projects/my-project)
Target Branch: main ⚠️ [PROTECTED BRANCH]  ──>  origin/main
Sync Status:   Ahead: 2 commit(s), Behind: 0 commit(s)
Action:        Commit: 'Add user authentication flow'

Warnings:
  ⚠️  Pushing directly to protected branch 'main'.

Changed Files (3 file(s), +84 / -12):
  M   src/auth.py                          (+65, -8)
  M   README.md                            (+19, -4)
  ??  config/auth.json                     (+12 lines, untracked)

Pending Commits to Push (2):
  • 8f3d1a2 Initial auth scaffold
  • 4e9c7b1 Implement JWT token verification
═══════════════════════════════════════════════════════════════

Continue? [y/N]:
```

---

## 🛑 Dangerous Command Guard

Use `gitpush guard <command>` (or `gitpush-guard <command>`) before executing risky Git operations:

### 1. Hard Reset (`reset --hard`)
Detects uncommitted modifications and unlinked commits before you lose them:

```text
Command: [WARNING ⚠️]
    git reset --hard HEAD~5

Changes that may be lost:
    5 commit(s)
    12 modified/staged file(s)

Risks & Warnings:
    ⚠️  All uncommitted changes in tracked files will be permanently discarded.
    ⚠️  12 uncommitted modified/staged file(s) will be lost immediately.
    ⚠️  5 commit(s) will be unlinked from current branch HEAD.

    Commits that will become unreachable:
      • cbc4db7 Add billing webhooks
      • 02bd1c5 Update stripe integration
      • 9033dd9 Fix invoice generator
      • a8eb29a Refactor customer portal
      • 97fd9b4 Update dependencies

Repository:
    my-project

Continue? [y/N]:
```

### 2. Guard Detects:
- **`reset --hard`**: Identifies uncommitted files and commits that will be orphaned.
- **`force push`**: Detects remote overwrite risks and protected branch overrides.
- **`deleting branches`**: Identifies unmerged commits that would be lost.
- **`cleaning untracked files`**: Warns of files/directories `git clean -fd` will permanently delete.
- **`checkout / restore`**: Flags uncommitted modifications about to be discarded.
- **`rebasing with uncommitted work`**: Warns of dirty working trees before rebase conflicts occur.
- **`pushing to protected branches`**: Direct pushes to `main`, `master`, `prod`, `dev`, etc.
- **`detached HEAD situations`**: Warns when working or committing on detached HEADs.

---

## 🛠️ Usage & Commands

| Command | Description |
|---|---|
| `gitpush "Commit message"` | Stages all changes, previews diffs, commits, and pushes. |
| `gitpush` | Pushes staged/unpushed changes with safety preview. |
| `gitpush -y` | Pushes immediately without confirmation prompt. |
| `gitpush --dry-run` | Shows the pre-push inspection and exits without changes. |
| `gitpush --force` | Safe force push using `--force-with-lease`. |
| `gitpush --tags` | Pushes all local tags. |
| `gitpush guard <git command>` | Inspects and guards any dangerous Git command. |
| `gitpush --init` | Initializes Git repo and creates default `.gitignore`. |
| `gitpush --new-repo <name>` | Creates a new GitHub repo and pushes in one step. |

---

## 🧠 New Repository Workflow

Create and publish a repository to GitHub in a single command:

```bash
# Public repo
gitpush "Initial commit" --new-repo my-awesome-project

# Private repo with description
gitpush "Initial commit" --new-repo secret-app --private --description "Internal tool"
```

---

## 🤝 Contributing

Contributions are welcome! Please feel free to open issues or submit pull requests on [GitHub](https://github.com/inevitablegs/gitpush).

---

## 📄 License

MIT © [Ganesh Sonawane](https://github.com/inevitablegs)
