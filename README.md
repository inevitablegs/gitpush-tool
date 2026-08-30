# GitPush Tool 🚀

[![PyPI version](https://img.shields.io/pypi/v/gitpush-tool.svg)](https://pypi.org/project/gitpush-tool/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

A supercharged Git CLI and safety tool that simplifies repository creation and pushing with intelligent defaults, rich pre-push diffstat inspection (`+++---` lines), and active safeguards against dangerous Git commands.

---

## ✨ Features

- **Smart Sync Engine (`gitpush sync`):** Intelligent single-command replacement for `git pull → git add → git commit → git push`. Automatically detects repository state (clean, dirty, ahead, behind, diverged) and safely synchronizes with remote.
- **Decision-Support Status Dashboard (`gitpush status`):** Actionable repository overview showing worktree breakdown, commit sync, intelligent next-step recommendations, and a 0-100 Repo Health score.
- **Interactive Undo Engine (`gitpush undo`):** Reversible and safe rollback for commits and pushes with detailed previews.
- **Pre-Push Safety & Diffstat Preview:** See changed files, line additions/deletions (`+X, -Y`), ahead/behind status, and pending commits before pushing.
- **Dangerous Git Operation Guard:** Analyzes and protects against risky actions (`reset --hard`, force pushes, deleting unmerged branches, dirty `git clean`, detached HEADs).
- **Protected Branch Safeguard:** Automatically detects and alerts when pushing or force-pushing to `main`, `master`, `prod`, `release`, or `dev`.
- **One-Command GitHub Repo Creation:** Initialize Git, create a remote GitHub repo, and push in a single step via GitHub CLI (`gh`).
- **Safe Force Pushing:** Uses `--force-with-lease` by default to avoid overwriting teammate commits.
- **Dry-Run Mode:** Preview your push inspection without modifying anything.
- **Non-Interactive & CI Friendly:** Skip prompts with `-y` or `--yes`.

---

## 🔄 Smart Sync Engine (`gitpush sync`)

Instead of running four separate commands every time:
```bash
git pull
git add .
git commit -m "..."
git push
```

Run **`gitpush sync`** (or `gitpush-sync`). GitPush detects your exact state and handles everything intelligently:

### Scenario A: Local Ahead
```text
Local:  3 commits ahead
Remote: 0 commits ahead

→ Safe to push
```
Prompts for push confirmation, or auto-pushes with `gitpush sync -y`.

### Scenario B: Branch Diverged
```text
Local:  2 commits ahead
Remote: 3 commits ahead

⚠ Branch has diverged.

Options:
  1. Rebase — replay your commits on top of remote (clean history)
  2. Merge  — merge remote into local (preserves history)
  3. Abort  — cancel sync
```

### Scenario C: Modified Files Detected
```text
Working Tree: 3 file(s) modified (+45, -8)

Commit before sync? [y/N]: y
Commit message (Enter for auto): Add user authentication
```

---

## 📦 Installation

```bash
pip install gitpush-tool
```

---

## 📊 Decision-Support Status Dashboard (`gitpush status`)

Instead of raw, cryptic Git output, `gitpush status` gives you structured decision support:

```text
Repository:  my-project
Branch:      feature/payment
Tracking:    origin/feature/payment

WORKTREE
────────────────────────
Modified       4
Added          2
Deleted        1
Untracked      3
Line Changes   +142, -18

COMMITS
────────────────────────
Ahead          3
Behind         1

PUSH / STATUS
────────────────────────
⚠ Remote has 1 commit(s) you don't have locally.

Recommended:
    git pull --rebase
    gitpush "Commit message"

Health:
    82/100 [████████░░] Good (Minor Action Needed)
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
| `gitpush sync` | Intelligent one-command sync (pull, commit dirty files, rebase/merge, push). |
| `gitpush sync -y` | Auto-confirms prompts and syncs immediately. |
| `gitpush sync -m "Msg"` | Sets custom commit message for modified files during sync. |
| `gitpush sync --rebase` | Prefers rebase automatically when branch has diverged. |
| `gitpush undo` | Interactive undo engine for commits and pushed history. |
| `gitpush status` | Decision-support status dashboard with recommendations. |
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
