# GitPush Tool

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python Version](https://img.shields.io/badge/Python-3.6%2B-blue.svg)](setup.py)
[![Dependencies](https://img.shields.io/badge/Dependencies-Zero%20(Standard%20Library)-brightgreen.svg)](setup.py)
[![Hackathon](https://img.shields.io/badge/Hackathon-Zero%20Dependency%202026-orange.svg)](LONG_DESCRIPTION.md#5-hackathon-context)
[![Track](https://img.shields.io/badge/Track-A%3A%20Developer%20Tools%20%26%20CLI-purple.svg)](LONG_DESCRIPTION.md#5-hackathon-context)

GitPush is a decision-support CLI and safety guard for common Git workflows. It provides pre-push inspection, diffstat line analysis (`+X, -Y`), dangerous operation interceptors (`reset --hard`, force pushes, unmerged branch deletions), an interactive undo engine with working-tree preservation, and a 0–100 repository health dashboard—engineered entirely with Python's standard library with zero runtime pip dependencies (`install_requires=[]`).

---

## 🏆 Hackathon Context

- **Event:** Zero Dependency 2026 — 72-Hour Hackathon
- **Organizer:** Hackathon Raptors
- **Track:** Track A — Developer Tools & CLI
- **Constraint:** Zero third-party runtime dependencies (`install_requires=[]`). Standard library only.

> For an in-depth technical breakdown, architectural analysis, and judging alignment, read the [Detailed Technical Long Description](LONG_DESCRIPTION.md).

---

## 🎯 Key Features

- **Decision-Support Status Dashboard (`gitpush status`):** Displays working tree status, ahead/behind tracking, contextual next-step recommendations, and a 0–100 repository health score.
- **Smart Synchronization Engine (`gitpush sync`):** Detects repository states (synchronized, local ahead, remote ahead, diverged, or dirty working tree) and safely handles pull, rebase, merge, and push steps.
- **Interactive Undo Engine (`gitpush undo`):** Inspects recent commits, distinguishes unpushed from pushed history, rewinds HEAD via soft reset to preserve working-tree changes, and safely rolls back pushed commits with `--force-with-lease` or `git revert`.
- **Dangerous Operation Guard (`gitpush guard <cmd>`):** Intercepts destructive commands (such as `reset --hard`, `push --force`, `branch -d/-D`, `clean -fd`), inspects uncommitted files and unreachable commits that would be lost, and requests explicit confirmation.
- **Pre-Push Diffstat Inspection:** Summarizes modified/staged/untracked files, calculates line additions and deletions (`+X, -Y`), and lists pending commits before pushing.
- **Protected Branch Safeguards:** Alerts before pushing or force-pushing directly to critical branches (`main`, `master`, `prod`, `release`, `dev`, `staging`).
- **Detached HEAD Detection:** Identifies detached HEAD states and advises on creating branches before commits become orphaned.
- **Automatic Commit Message Generation:** Generates lightweight commit messages from diff statistics (e.g., `Update foo.py (+5, -2)` or `Update 3 files (+10, -4)`).
- **One-Command GitHub Repository Creation (`gitpush --new-repo`):** Initializes local Git repositories, creates remote GitHub repositories, and pushes upstream in a single command using GitHub CLI (`gh`).
- **Safe Force Pushing:** Enforces `--force-with-lease` rather than blind `--force` when force pushing is requested.
- **Dry-Run Inspection (`gitpush --dry-run`):** Generates full pre-push diagnostics without altering repository state.

---

## 💡 Why GitPush?

Git provides unmatched flexibility, but common daily tasks frequently cause workflow friction:

1. **Accidental Loss of Work:** Commands like `git reset --hard` or `git clean -fd` permanently discard uncommitted changes without itemized impact warnings.
2. **Push Uncertainty:** Developers often push without immediate visibility into pending commits, remote divergence, or accidental direct pushes to protected branches.
3. **Complex Sync Routines:** Synchronizing diverged branches or dirty worktrees requires remembering specific sequences of `fetch`, `rebase`, `stash`, `merge`, and `push`.
4. **Heavy CLI Abstractions:** Many Git helpers hide Git completely behind custom abstractions or require dozens of megabytes of third-party dependencies (`GitPython`, `click`, `rich`, `requests`).

**GitPush takes a different approach:** It acts as a transparent decision-support layer. It analyzes native Git state, surfaces exact risks with line-level diff statistics, and guides developers to the right action without replacing Git primitives or adding runtime dependencies.

---

## ⚡ Zero Dependency Engineering

GitPush was built strictly under the Zero Dependency constraint:

- **Manifest:** `install_requires=[]` in `setup.py`
- **Runtime Dependencies:** 0 external pip packages
- **Standard Library Primitives:** Relies exclusively on built-in Python modules:
  - `argparse` & `sys` for CLI parsing and dispatching
  - `subprocess` for native Git plumbing and porcelain execution
  - `pathlib`, `os`, `shutil`, `tempfile` for filesystem and process management
  - `urllib.request` & `json` for optional GitHub CLI asset verification
  - `unittest` for automated test suites

*Note: Git itself is an external system tool invoked through standard subprocess execution, not a Python package dependency.*

---

## 🏗️ Architecture

```text
                                  User Terminal
                                        │
                                        ▼
                                 ┌──────────────┐
                                 │ gitpush CLI  │ (cli.py)
                                 └──────┬───────┘
                                        │
         ┌──────────────────────────────┼──────────────────────────────┐
         ▼                              ▼                              ▼
┌──────────────────┐          ┌───────────────────┐          ┌──────────────────┐
│  Safety Engine   │          │   Status Engine   │          │   Sync Engine    │
│  (safety.py)     │          │   (status.py)     │          │   (sync.py)      │
│  • Diffstat      │          │  • Health Score   │          │  • Auto-commit   │
│  • Danger Guard  │          │  • Recommendations│          │  • Rebase/Merge  │
│  • Protected Ref │          │  • Worktree Stat  │          │  • Push Flow     │
└────────┬─────────┘          └─────────┬─────────┘          └────────┬─────────┘
         │                              │                             │
         └──────────────────────────────┼─────────────────────────────┘
                                        │
                                        ▼
                               ┌──────────────────┐
                               │   Undo Engine    │ (undo.py)
                               │  • Soft Reset    │
                               │  • Pushed Check  │
                               │  • Force-w/-Lease│
                               └────────┬─────────┘
                                        │
                                        ▼
                                Native Git Binary
                                        │
                                        ▼
                            Local Repository & Remote
```

---

## 📦 Installation

### From Source (Zero Runtime Dependencies)

Clone the repository and install using standard Python packaging:

```bash
git clone https://github.com/inevitablegs/gitpush.git
cd gitpush-tool
pip install .
```

For editable local development:

```bash
pip install -e .
```

### Verification of Zero Dependencies

You can verify that no external runtime dependencies are specified:

```bash
python setup.py --requires
# Returns nothing (empty list)
```

---

## 🚀 Quick Start

| Command | Description |
|---|---|
| `gitpush status` | Displays the decision-support status dashboard and repository health score. |
| `gitpush "Add user authentication"` | Previews changed files and diffstat, commits uncommitted changes, and pushes. |
| `gitpush "Add user authentication" -y` | Stages, commits, and pushes immediately without interactive confirmation. |
| `gitpush --dry-run` | Runs full pre-push diagnostics and diffstat preview without modifying anything. |
| `gitpush sync` | Detects repository state (ahead, behind, diverged, dirty) and synchronizes with remote. |
| `gitpush sync -y` | Auto-confirms prompts and synchronizes immediately. |
| `gitpush sync --rebase` | Prefers rebase automatically when branch divergence is detected. |
| `gitpush undo` | Opens the interactive undo menu for recent commits. |
| `gitpush undo commit` | Rewinds the latest commit locally while keeping all file modifications in your worktree. |
| `gitpush undo push` | Rewinds local commit and safely rolls back remote branch using `--force-with-lease`. |
| `gitpush guard git reset --hard HEAD~5` | Evaluates lost commits and dirty files before executing a destructive reset. |
| `gitpush --force` | Safe force push using `--force-with-lease`. |
| `gitpush --init` | Initializes a Git repository and generates a standard `.gitignore`. |
| `gitpush --new-repo my-project` | Creates a new GitHub repository and pushes local code via GitHub CLI (`gh`). |

---

## 🔄 Example Workflow

### 1. Check Repository State & Health

```bash
gitpush status
```

```text
Repository:  my-app
Branch:      feature/billing
Tracking:    origin/feature/billing

WORKTREE
────────────────────────
Modified       2
Untracked      1
Line Changes   +48, -6

COMMITS
────────────────────────
Ahead          1
Behind         0

PUSH / STATUS
────────────────────────
Ready to commit 3 change(s) and push 1 commit(s).

Recommended:
    gitpush "Commit message"

Health:
    90/100 [█████████░] Excellent (Clean & Ready)
```

### 2. Inspect Changes & Push

```bash
gitpush "Integrate Stripe payment webhook"
```

```text
═══════════════════════════════════════════════════════════════
 🚀 GITPUSH PRE-PUSH INSPECTION & SUMMARY
═══════════════════════════════════════════════════════════════

Repository:    my-app (E:/projects/my-app)
Target Branch: feature/billing  ──>  origin/feature/billing
Sync Status:   Ahead: 1 commit(s)
Action:        Commit: 'Integrate Stripe payment webhook'

Changed Files (3 file(s), +48 / -6):
  M   src/billing.py                       (+42, -6)
  M   tests/test_billing.py                (+6, -0)
  ??  config/stripe.json                   (+15 lines, untracked)

Pending Commits to Push (1):
  • 8a1b2c3 Add webhook signature validation
═══════════════════════════════════════════════════════════════

Continue? [y/N]: y
```

### 3. Guarding Risky Operations

```bash
gitpush guard git reset --hard HEAD~3
```

```text
Command: [WARNING ⚠️]
    git reset --hard HEAD~3

Changes that may be lost:
    3 commit(s)
    2 modified/staged file(s)

Risks & Warnings:
    ⚠️  All uncommitted changes in tracked files will be permanently discarded.
    ⚠️  2 uncommitted modified/staged file(s) will be lost immediately.
    ⚠️  3 commit(s) will be unlinked from current branch HEAD.

Repository:
    my-app

Continue? [y/N]:
```

### 4. Undoing a Commit Safely

```bash
gitpush undo commit
```

```text
═══════════════════════════════════════════════════════════════
 ⏪ GITPUSH UNDO INSPECTION
═══════════════════════════════════════════════════════════════

Target Action:  Commit 8a1b2c3: Integrate Stripe payment webhook
Branch:         feature/billing
Status:         Local only (Unpushed) ✔

This will:
  ✓ Keep all your file changes in your working tree
  ✗ Remove the commit from local history cleanly

═══════════════════════════════════════════════════════════════

Continue? [y/N]: y

✅ Successfully rewound commit 8a1b2c3!
📁 All changes are now preserved in your working directory.
```

---

## 🛡️ Safety Model

GitPush enforces safety without removing developer control:

- **Soft Resets by Default:** Undoing commits uses soft resets (`git reset --soft HEAD~1`), preserving working directory edits.
- **Lease-Protected Force Pushes:** Replaces blind force pushes (`git push -f`) with `--force-with-lease` to prevent overwriting commits pushed by collaborators.
- **Protected Branch Alerts:** Warns when an operation targets `main`, `master`, `prod`, `release`, `staging`, or `dev`.
- **Pre-Execution Dry-Run Inspection:** Evaluates unmerged commits, uncommitted file modifications, and line diffs before destructive commands proceed.
- **Detached HEAD Prevention:** Warns when HEAD is detached so commits are not accidentally orphaned.

---

## 📊 Repository Health Score Calculation

The health score in `gitpush status` is a heuristic decision-support metric calculated from repository state (0–100):

| Condition | Score Impact | Rationale |
|---|---|---|
| Clean & In-Sync Baseline | `100` | Repository is synchronized and clean. |
| Unresolved Conflicts (`unmerged`) | `-20` per file (max `-40`) | Active merge or rebase conflicts block normal operations. |
| Detached HEAD | `-25` | New commits will become unreachable when switching branches. |
| Diverged Branches | `-20` | Remote and local have conflicting histories requiring rebase or merge. |
| Commits Behind Remote | `-3` per commit (max `-15`) | Local branch is outdated. |
| Dirty Worktree | `-5` (>5 files), `-10` (>10 files), `-15` (>20 files) | High volume of uncommitted modifications. |
| Stash Accumulation | `-5` (>5 stashes), `-10` (>10 stashes) | Stale stashes cluttering workspace context. |

---

## 🧪 Testing

The test suite runs with Python's standard `unittest` module and validates real Git interactions inside temporary repositories:

```bash
python -m unittest discover tests/
```

### Test Coverage Highlights

- **`tests/test_status.py`:** Validates worktree file categorization (modified, added, untracked), repository health scoring (100 for clean repos, <50 for degraded states), behind-remote recommendation generation, and dashboard layout formatting.
- **`tests/test_sync.py`:** Uses isolated bare repositories (`git init --bare`) and local clones to test auto-generated commit message formatting (`Update foo.py (+5, -2)`), automatic staging and committing, synchronized state handling, local-ahead pushes, dirty worktree commits, and diverged rebase synchronization across multi-clone setups.
- **`tests/test_undo.py`:** Tests commit metadata extraction, recent action menu formatting, and verifies that undoing a commit rewinds HEAD while retaining all modified files in the working directory.

---

## 🔍 Zero-Dependency Verification

You can verify that GitPush contains zero external runtime dependencies by checking the package definitions:

1. **`setup.py` Inspection:**
   ```python
   install_requires=[]
   ```
2. **`pyproject.toml` Inspection:**
   ```toml
   [build-system]
   requires = ["setuptools"]
   build-backend = "setuptools.build_meta"
   ```
3. **Environment Audit:**
   No third-party packages need to be downloaded from PyPI during installation or runtime.

---

## 📄 Standard Library Log (STDLIB.md)

How was GitPush built without third-party packages?

Read [STDLIB.md](STDLIB.md) for the standard-library substitution log documenting how modules like `subprocess`, `argparse`, `urllib.request`, `tempfile`, and `shutil` replace packages such as `GitPython`, `click`, `rich`, and `requests`.

---

## 📂 Project Structure

```text
gitpush-tool/
├── README.md               # GitHub landing page & quick overview
├── LONG_DESCRIPTION.md     # Detailed technical & hackathon documentation
├── STDLIB.md               # Standard library package substitution log
├── LICENSE                 # MIT License
├── MANIFEST.in             # Source distribution manifest
├── pyproject.toml          # PEP 517 build configuration
├── setup.py                # Package metadata (install_requires=[])
├── gitpush/
│   ├── __init__.py         # Version definition (0.4.3)
│   ├── __doc__.py          # Docstring summary
│   ├── cli.py              # CLI entry point, argument parsing & dispatch
│   ├── safety.py           # Pre-push inspection, diffstat & danger guard
│   ├── status.py           # Status dashboard, health score & recommendations
│   ├── sync.py             # Single-command synchronization engine
│   └── undo.py             # Interactive commit & push undo engine
└── tests/
    ├── test_cli.py         # CLI tests
    ├── test_safety.py      # Safety tests
    ├── test_status.py      # Status & health score tests
    ├── test_sync.py        # Sync scenario tests with bare remote repos
    └── test_undo.py        # Undo & worktree preservation tests
```

---

## 📋 Hackathon Compliance Checklist

- [x] **Zero Third-Party Runtime Dependencies:** `install_requires=[]` in `setup.py`
- [x] **Track A Focus:** Developer Tools & CLI
- [x] **Single Command Build & Install:** Standard Python build system (`pip install .`)
- [x] **Automated Test Suite:** Standard `unittest` suite covering status, sync, and undo flows
- [x] **Concise Landing Page:** `README.md`
- [x] **Detailed Technical Explanation:** `LONG_DESCRIPTION.md`
- [x] **Standard Library Substitution Documentation:** `STDLIB.md`
- [x] **Permissive Open-Source License:** MIT License

---

## 🗺️ Roadmap & Future Work

The following features represent planned future enhancements (not currently in v0.4.3):

- **Local Configuration (`.gitpushrc`):** Support for custom protected branch lists and custom health score weighting.
- **Interactive Patch Staging:** Interactive hunk-by-hunk diff selector using native terminal inputs.
- **Commit Signing Verification:** Diagnostic warnings for missing GPG/SSH commit signatures on protected branches.

---

## 🤝 Contributing

Contributions are welcome. Since this project is committed to zero external runtime dependencies, all pull requests must use only the Python standard library.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/improvement`)
3. Run test suite (`python -m unittest discover tests/`)
4. Commit your changes (`gitpush "Add feature"`)
5. Open a Pull Request on [GitHub](https://github.com/inevitablegs/gitpush)

---

## 📄 License

Distributed under the [MIT License](LICENSE). Copyright © 2025 Ganesh Sonawane.

---

## 👤 Author

**Ganesh Sonawane**
- GitHub: [@inevitablegs](https://github.com/inevitablegs)
- Repository: [https://github.com/inevitablegs/gitpush](https://github.com/inevitablegs/gitpush)
