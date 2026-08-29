"""
GitPush Safety Engine
Provides repository inspection, diffstat calculation (+/- line changes),
branch ahead/behind tracking, protected branch guard, detached HEAD detection,
and deep risk analysis for dangerous Git operations.
"""

import os
import sys
import subprocess
import shutil
import re
from typing import Optional, List, Dict, Tuple, Any

# Reconfigure stdout/stderr encoding if possible for Windows emoji support
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Common protected branch names
DEFAULT_PROTECTED_BRANCHES = {
    "main", "master", "prod", "production", "release", "releases",
    "staging", "live", "stable", "dev", "develop", "development"
}

# Color / Style helpers (gracefully falls back if color not supported)
class Style:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"

def supports_color() -> bool:
    """Check if the current terminal supports ANSI color escape codes."""
    if os.environ.get("NO_COLOR"):
        return False
    if not hasattr(sys.stdout, "isatty") or not sys.stdout.isatty():
        return False
    if sys.platform == "win32":
        return os.environ.get("ANSICON") is not None or "WT_SESSION" in os.environ or os.environ.get("TERM_PROGRAM") is not None or "ConEmuANSI" in os.environ or os.environ.get("TERM") == "xterm" or True
    return True

_COLOR_ENABLED = supports_color()

def colorize(text: str, *styles: str) -> str:
    """Apply styling if color is enabled."""
    if not _COLOR_ENABLED or not styles:
        return text
    prefix = "".join(styles)
    return f"{prefix}{text}{Style.RESET}"


def run_git(args: List[str], check: bool = False, capture: bool = True, cwd: Optional[str] = None) -> subprocess.CompletedProcess:
    """Helper to run a git command safely."""
    return subprocess.run(
        ["git"] + args,
        check=check,
        capture_output=capture,
        text=True,
        cwd=cwd
    )


# --- Repository & Branch Info ---

def is_git_repo(cwd: Optional[str] = None) -> bool:
    """Check if the current directory is inside a Git working tree."""
    res = run_git(["rev-parse", "--is-inside-work-tree"], cwd=cwd)
    return res.returncode == 0 and res.stdout.strip() == "true"


def get_repo_root(cwd: Optional[str] = None) -> Optional[str]:
    """Get the absolute path to the repository root."""
    res = run_git(["rev-parse", "--show-toplevel"], cwd=cwd)
    if res.returncode == 0:
        return res.stdout.strip()
    return None


def get_repo_name(cwd: Optional[str] = None) -> str:
    """Get the repository directory name."""
    root = get_repo_root(cwd)
    if root:
        return os.path.basename(os.path.abspath(root))
    return os.path.basename(os.getcwd())


def is_detached_head(cwd: Optional[str] = None) -> bool:
    """Check if the repository is in a detached HEAD state."""
    res = run_git(["symbolic-ref", "-q", "HEAD"], cwd=cwd)
    return res.returncode != 0


def get_current_branch(cwd: Optional[str] = None) -> str:
    """Get the current branch name or short commit SHA if detached."""
    if is_detached_head(cwd):
        res = run_git(["rev-parse", "--short", "HEAD"], cwd=cwd)
        sha = res.stdout.strip() if res.returncode == 0 else "HEAD"
        return f"HEAD (detached at {sha})"
    
    res = run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=cwd)
    if res.returncode == 0:
        branch = res.stdout.strip()
        if branch != "HEAD":
            return branch
    return "main"


def is_protected_branch(branch_name: str) -> bool:
    """Check if branch is commonly protected."""
    clean_name = branch_name.lower().split('/')[-1].strip()
    return clean_name in DEFAULT_PROTECTED_BRANCHES


def get_ahead_behind(remote: str = "origin", branch: str = "main", cwd: Optional[str] = None) -> Tuple[int, int]:
    """
    Get (behind_count, ahead_count) relative to remote tracking branch.
    """
    try:
        # Check if remote ref exists
        ref = f"{remote}/{branch}"
        res = run_git(["rev-list", "--left-right", "--count", f"{ref}...HEAD"], cwd=cwd)
        if res.returncode == 0:
            parts = res.stdout.strip().split()
            if len(parts) == 2:
                behind, ahead = int(parts[0]), int(parts[1])
                return behind, ahead
    except Exception:
        pass
    return 0, 0


# --- Diff & File Change Statistics ---

class FileChangeStat:
    def __init__(self, path: str, status: str, additions: int = 0, deletions: int = 0, is_binary: bool = False, is_untracked: bool = False):
        self.path = path
        self.status = status # 'M', 'A', 'D', 'R', 'C', 'U', '??'
        self.additions = additions
        self.deletions = deletions
        self.is_binary = is_binary
        self.is_untracked = is_untracked

    @property
    def diff_stat_str(self) -> str:
        if self.is_untracked:
            if self.additions > 0:
                return colorize(f"(+{self.additions} lines, untracked)", Style.GREEN)
            return colorize("(untracked)", Style.DIM)
        if self.is_binary:
            return colorize("(binary)", Style.CYAN)
        plus = colorize(f"+{self.additions}", Style.GREEN) if self.additions > 0 else "+0"
        minus = colorize(f"-{self.deletions}", Style.RED) if self.deletions > 0 else "-0"
        return f"({plus}, {minus})"


def get_diffstat_summary(cwd: Optional[str] = None) -> Dict[str, Any]:
    """
    Compute comprehensive file modifications and line diff additions/deletions.
    Returns:
        {
            "files": List[FileChangeStat],
            "total_additions": int,
            "total_deletions": int,
            "modified_count": int,
            "staged_count": int,
            "untracked_count": int,
            "has_changes": bool
        }
    """
    if not is_git_repo(cwd):
        return {
            "files": [],
            "total_additions": 0,
            "total_deletions": 0,
            "modified_count": 0,
            "staged_count": 0,
            "untracked_count": 0,
            "has_changes": False
        }

    # 1. Get porcelain status
    res_status = run_git(["status", "--porcelain=v1", "-uall"], cwd=cwd)
    status_lines = res_status.stdout.splitlines() if res_status.returncode == 0 else []

    status_map: Dict[str, str] = {}
    untracked_files: List[str] = []
    staged_count = 0
    unstaged_count = 0

    for line in status_lines:
        if not line.strip():
            continue
        index_status = line[0]
        work_status = line[1]
        file_path = line[3:].strip()
        if " -> " in file_path:
            file_path = file_path.split(" -> ")[-1].strip()

        if index_status == '?' and work_status == '?':
            untracked_files.append(file_path)
            status_map[file_path] = "??"
        else:
            if index_status != ' ' and index_status != '?':
                staged_count += 1
            if work_status != ' ' and work_status != '?':
                unstaged_count += 1
            code = index_status if index_status != ' ' else work_status
            status_map[file_path] = code

    # 2. Get numstat for both staged and unstaged changes against HEAD
    numstat_map: Dict[str, Tuple[int, int, bool]] = {} # path -> (additions, deletions, is_binary)
    
    # Check if there are any commits in repo
    has_commits = run_git(["rev-parse", "--verify", "HEAD"], cwd=cwd).returncode == 0

    if has_commits:
        # Diff against HEAD (includes both staged and working tree modifications)
        res_numstat = run_git(["diff", "HEAD", "--numstat"], cwd=cwd)
        if res_numstat.returncode == 0:
            for line in res_numstat.stdout.splitlines():
                parts = line.split("\t")
                if len(parts) >= 3:
                    add_str, del_str, p = parts[0], parts[1], parts[2]
                    if " => " in p:
                        # Handle renames
                        p = p.split(" => ")[-1].rstrip("}").strip()
                    if add_str == "-" and del_str == "-":
                        numstat_map[p] = (0, 0, True)
                    else:
                        numstat_map[p] = (int(add_str) if add_str.isdigit() else 0,
                                          int(del_str) if del_str.isdigit() else 0,
                                          False)
    else:
        # Initial commit pending: check diff of staged
        res_numstat = run_git(["diff", "--cached", "--numstat"], cwd=cwd)
        if res_numstat.returncode == 0:
            for line in res_numstat.stdout.splitlines():
                parts = line.split("\t")
                if len(parts) >= 3:
                    add_str, del_str, p = parts[0], parts[1], parts[2]
                    if add_str == "-" and del_str == "-":
                        numstat_map[p] = (0, 0, True)
                    else:
                        numstat_map[p] = (int(add_str) if add_str.isdigit() else 0,
                                          int(del_str) if del_str.isdigit() else 0,
                                          False)

    # 3. For untracked files, calculate line count if readable text
    repo_root = get_repo_root(cwd) or os.getcwd()
    for uf in untracked_files:
        full_path = os.path.join(repo_root, uf)
        if os.path.isfile(full_path):
            try:
                with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                    line_count = sum(1 for _ in f)
                numstat_map[uf] = (line_count, 0, False)
            except Exception:
                numstat_map[uf] = (0, 0, True)

    # 4. Construct FileChangeStat list
    all_files: List[FileChangeStat] = []
    total_adds = 0
    total_dels = 0

    all_paths = sorted(set(list(status_map.keys()) + list(numstat_map.keys())))
    for path in all_paths:
        status = status_map.get(path, "M")
        adds, dels, is_bin = numstat_map.get(path, (0, 0, False))
        is_untracked = (status == "??")
        total_adds += adds
        total_dels += dels
        all_files.append(FileChangeStat(
            path=path,
            status=status,
            additions=adds,
            deletions=dels,
            is_binary=is_bin,
            is_untracked=is_untracked
        ))

    return {
        "files": all_files,
        "total_additions": total_adds,
        "total_deletions": total_dels,
        "modified_count": len(all_files),
        "staged_count": staged_count,
        "untracked_count": len(untracked_files),
        "has_changes": len(all_files) > 0
    }


def get_pending_commits(remote: str = "origin", branch: str = "main", cwd: Optional[str] = None) -> List[Tuple[str, str]]:
    """
    Get list of (short_sha, subject) for local commits not yet on remote.
    """
    commits = []
    ref = f"{remote}/{branch}..HEAD"
    res = run_git(["log", ref, "--oneline", "-n", "10"], cwd=cwd)
    if res.returncode == 0 and res.stdout.strip():
        for line in res.stdout.strip().splitlines():
            parts = line.split(" ", 1)
            if len(parts) == 2:
                commits.append((parts[0], parts[1]))
            elif len(parts) == 1:
                commits.append((parts[0], ""))
    return commits


# --- Dangerous Operation Analyzer ---

class DangerousOperationReport:
    """Holds risks, warnings, and details about a git operation."""
    def __init__(self, command_str: str, operation_name: str):
        self.command_str = command_str
        self.operation_name = operation_name
        self.is_dangerous: bool = False
        self.severity: str = "INFO" # "INFO", "WARNING", "HIGH_RISK", "CRITICAL"
        self.risks: List[str] = []
        self.lost_items: Dict[str, Any] = {} # e.g. {"commits": 5, "modified_files": 12, ...}
        self.extra_details: List[str] = []

    def add_risk(self, risk: str, severity: str = "WARNING"):
        self.risks.append(risk)
        self.is_dangerous = True
        if severity == "CRITICAL" or self.severity == "CRITICAL":
            self.severity = "CRITICAL"
        elif severity == "HIGH_RISK" or self.severity == "HIGH_RISK":
            self.severity = "HIGH_RISK"
        elif severity == "WARNING":
            if self.severity != "HIGH_RISK" and self.severity != "CRITICAL":
                self.severity = "WARNING"


class DangerousOperationAnalyzer:
    """Analyzes CLI actions and repository state to detect dangerous operations."""

    @staticmethod
    def analyze_reset_hard(target_ref: str = "HEAD~1", cwd: Optional[str] = None) -> DangerousOperationReport:
        """
        Analyze 'git reset --hard <ref>'.
        Detects commits that will be lost from HEAD to target_ref,
        and modified/staged files that will be wiped out.
        """
        report = DangerousOperationReport(f"git reset --hard {target_ref}", "Hard Reset (reset --hard)")
        report.add_risk("All uncommitted changes in tracked files will be permanently discarded.", "HIGH_RISK")

        # 1. Check uncommitted changes
        diff_info = get_diffstat_summary(cwd)
        mod_files = [f for f in diff_info["files"] if not f.is_untracked]
        if mod_files:
            report.lost_items["modified_files"] = len(mod_files)
            report.add_risk(f"{len(mod_files)} uncommitted modified/staged file(s) will be lost immediately.", "HIGH_RISK")

        # 2. Check commits that will be lost
        res = run_git(["rev-list", "--count", f"{target_ref}..HEAD"], cwd=cwd)
        if res.returncode == 0 and res.stdout.strip().isdigit():
            lost_commit_count = int(res.stdout.strip())
            if lost_commit_count > 0:
                report.lost_items["commits"] = lost_commit_count
                report.add_risk(f"{lost_commit_count} commit(s) will be unlinked from current branch HEAD.", "HIGH_RISK")
                
                # Fetch commit list
                res_commits = run_git(["log", f"{target_ref}..HEAD", "--oneline"], cwd=cwd)
                if res_commits.returncode == 0:
                    report.extra_details.append("Commits that will become unreachable:")
                    for c in res_commits.stdout.strip().splitlines()[:5]:
                        report.extra_details.append(f"  • {c}")
                    if lost_commit_count > 5:
                        report.extra_details.append(f"  • ... and {lost_commit_count - 5} more")

        return report

    @staticmethod
    def analyze_force_push(remote: str = "origin", branch: str = "main", cwd: Optional[str] = None) -> DangerousOperationReport:
        """
        Analyze 'git push --force'.
        Detects remote overwrite risks and protected branch force pushes.
        """
        report = DangerousOperationReport(f"git push --force {remote} {branch}", "Force Push")
        
        is_prot = is_protected_branch(branch)
        if is_prot:
            report.add_risk(f"Target '{branch}' is a PROTECTED BRANCH! Force pushing may overwrite teammates' commits.", "CRITICAL")
        else:
            report.add_risk(f"Force pushing will overwrite the remote history on '{branch}'.", "HIGH_RISK")

        # Check if remote has commits we are behind on
        behind, ahead = get_ahead_behind(remote, branch, cwd)
        if behind > 0:
            report.lost_items["remote_commits_overwritten"] = behind
            report.add_risk(f"{behind} remote commit(s) will be overwritten and lost on the server.", "CRITICAL")

        return report

    @staticmethod
    def analyze_branch_delete(branch_name: str, force: bool = False, cwd: Optional[str] = None) -> DangerousOperationReport:
        """
        Analyze 'git branch -d / -D <branch>'.
        """
        cmd = f"git branch {'-D' if force else '-d'} {branch_name}"
        report = DangerousOperationReport(cmd, "Delete Branch")

        if is_protected_branch(branch_name):
            report.add_risk(f"'{branch_name}' is a protected branch name! Deleting it may break CI/CD or production.", "CRITICAL")

        # Check if merged into HEAD
        res = run_git(["branch", "--merged", "HEAD"], cwd=cwd)
        merged_branches = [b.strip().lstrip("* ") for b in res.stdout.splitlines()] if res.returncode == 0 else []
        if branch_name not in merged_branches:
            # Unmerged branch
            res_unmerged = run_git(["rev-list", "--count", f"HEAD..{branch_name}"], cwd=cwd)
            unmerged_count = int(res_unmerged.stdout.strip()) if res_unmerged.returncode == 0 and res_unmerged.stdout.strip().isdigit() else 0
            if unmerged_count > 0:
                report.lost_items["unmerged_commits"] = unmerged_count
                report.add_risk(f"Branch '{branch_name}' contains {unmerged_count} unmerged commit(s) that may be lost.", "HIGH_RISK")
            else:
                report.add_risk(f"Branch '{branch_name}' is not fully merged into current HEAD.", "WARNING")

        return report

    @staticmethod
    def analyze_clean(force: bool = True, remove_dirs: bool = True, cwd: Optional[str] = None) -> DangerousOperationReport:
        """
        Analyze 'git clean -f / -fd / -fx'.
        """
        cmd = f"git clean {'-f' if force else ''}{'d' if remove_dirs else ''}"
        report = DangerousOperationReport(cmd.strip(), "Clean Untracked Files")
        report.add_risk("Untracked files and directories will be PERMANENTLY deleted from disk (cannot be recovered with Git).", "HIGH_RISK")

        # Dry-run clean
        clean_args = ["clean", "-n"]
        if remove_dirs:
            clean_args.append("-d")
        res = run_git(clean_args, cwd=cwd)
        if res.returncode == 0 and res.stdout.strip():
            lines = res.stdout.strip().splitlines()
            report.lost_items["untracked_files"] = len(lines)
            report.extra_details.append(f"Found {len(lines)} file(s)/directory(s) to be removed:")
            for l in lines[:8]:
                report.extra_details.append(f"  • {l.replace('Would remove ', '')}")
            if len(lines) > 8:
                report.extra_details.append(f"  • ... and {len(lines) - 8} more")

        return report

    @staticmethod
    def analyze_checkout_discard(cwd: Optional[str] = None) -> DangerousOperationReport:
        """
        Analyze discarding uncommitted modifications via checkout/restore.
        """
        report = DangerousOperationReport("git checkout -- . / git restore .", "Discard Working Tree Changes")
        report.add_risk("All unstaged local modifications will be permanently discarded.", "HIGH_RISK")
        diff_info = get_diffstat_summary(cwd)
        mod_files = [f for f in diff_info["files"] if not f.is_untracked]
        if mod_files:
            report.lost_items["modified_files"] = len(mod_files)
        return report

    @staticmethod
    def analyze_rebase_with_uncommitted(cwd: Optional[str] = None) -> DangerousOperationReport:
        """
        Analyze rebasing when there is uncommitted work.
        """
        report = DangerousOperationReport("git rebase", "Rebase with Dirty Working Tree")
        diff_info = get_diffstat_summary(cwd)
        if diff_info["has_changes"]:
            report.add_risk("You have uncommitted modifications. Rebase may fail or cause complex merge conflicts.", "WARNING")
            report.lost_items["modified_files"] = diff_info["modified_count"]
        return report

    @classmethod
    def analyze_arbitrary_command(cls, cmd_args: List[str], cwd: Optional[str] = None) -> Optional[DangerousOperationReport]:
        """
        Parses arbitrary git command arguments and detects dangerous patterns.
        """
        if not cmd_args:
            return None

        # Normalize command: remove leading 'git' if passed e.g. ['git', 'reset', '--hard']
        args = [a for a in cmd_args]
        if args and args[0].lower() == "git":
            args = args[1:]
        if not args:
            return None

        subcmd = args[0].lower()

        # 1. reset --hard
        if subcmd == "reset" and "--hard" in args:
            target = "HEAD"
            for a in args[1:]:
                if not a.startswith("-"):
                    target = a
                    break
            return cls.analyze_reset_hard(target, cwd)

        # 2. push --force / -f / --force-with-lease
        if subcmd == "push":
            has_force = any(f in args for f in ["--force", "-f", "--force-with-lease"])
            # Extract remote & branch
            remote = "origin"
            branch = get_current_branch(cwd)
            positional = [a for a in args[1:] if not a.startswith("-")]
            if len(positional) >= 1:
                remote = positional[0]
            if len(positional) >= 2:
                branch = positional[1]

            # Check branch deletion via push
            if any(a.startswith(":") or a == "--delete" for a in args):
                del_branch = branch
                for a in positional:
                    if a.startswith(":"):
                        del_branch = a[1:]
                return cls.analyze_branch_delete(del_branch, force=True, cwd=cwd)

            if has_force:
                return cls.analyze_force_push(remote, branch, cwd)
            
            # Check push to protected branch without force
            if is_protected_branch(branch):
                report = DangerousOperationReport(f"git {' '.join(args)}", "Push to Protected Branch")
                report.add_risk(f"You are pushing directly to protected branch '{branch}'.", "WARNING")
                return report

        # 3. branch -d / -D
        if subcmd == "branch" and any(f in args for f in ["-d", "-D", "--delete"]):
            force = "-D" in args
            target_branch = ""
            for a in args[1:]:
                if not a.startswith("-"):
                    target_branch = a
                    break
            if target_branch:
                return cls.analyze_branch_delete(target_branch, force=force, cwd=cwd)

        # 4. clean -f / -fd / -fx
        if subcmd == "clean" and any(f in args for f in ["-f", "-force", "-fd", "-df", "-fx", "-xf"]):
            remove_dirs = any("d" in a for a in args if a.startswith("-"))
            return cls.analyze_clean(force=True, remove_dirs=remove_dirs, cwd=cwd)

        # 5. checkout -- . / restore . / checkout -f
        if (subcmd == "checkout" and ("--" in args or "-f" in args or "--force" in args)) or \
           (subcmd == "restore" and ("." in args or "--staged" in args or "--worktree" in args)):
            return cls.analyze_checkout_discard(cwd)

        # 6. rebase with uncommitted changes
        if subcmd == "rebase":
            diff = get_diffstat_summary(cwd)
            if diff["has_changes"]:
                return cls.analyze_rebase_with_uncommitted(cwd)

        return None


# --- Formatted UI & Warning Presentation ---

def format_danger_box(report: DangerousOperationReport, repo_name: Optional[str] = None) -> str:
    """
    Format a dangerous operation report matching the clean, elegant specification:

    Command:
        git reset --hard HEAD~5

    Changes that may be lost:
        5 commits
        12 modified files

    Repository:
        my-project
    """
    lines = []
    repo = repo_name or get_repo_name()

    # Header with severity badge
    badge = ""
    if report.severity == "CRITICAL":
        badge = colorize(" [CRITICAL DANGER 🛑]", Style.BOLD, Style.RED)
    elif report.severity in ("HIGH_RISK", "WARNING"):
        badge = colorize(" [WARNING ⚠️]", Style.BOLD, Style.YELLOW)

    lines.append(colorize("Command:", Style.BOLD) + badge)
    lines.append(f"    {colorize(report.command_str, Style.CYAN)}")
    lines.append("")

    if report.lost_items:
        lines.append(colorize("Changes that may be lost:", Style.BOLD, Style.RED if report.severity in ("CRITICAL", "HIGH_RISK") else Style.YELLOW))
        if "commits" in report.lost_items:
            lines.append(f"    {report.lost_items['commits']} commit(s)")
        if "remote_commits_overwritten" in report.lost_items:
            lines.append(f"    {report.lost_items['remote_commits_overwritten']} remote commit(s) on server")
        if "modified_files" in report.lost_items:
            lines.append(f"    {report.lost_items['modified_files']} modified/staged file(s)")
        if "untracked_files" in report.lost_items:
            lines.append(f"    {report.lost_items['untracked_files']} untracked file(s)")
        if "unmerged_commits" in report.lost_items:
            lines.append(f"    {report.lost_items['unmerged_commits']} unmerged commit(s)")
        lines.append("")

    if report.risks:
        lines.append(colorize("Risks & Warnings:", Style.BOLD))
        for r in report.risks:
            lines.append(f"    ⚠️  {r}")
        lines.append("")

    if report.extra_details:
        for d in report.extra_details:
            lines.append(f"    {colorize(d, Style.DIM)}")
        lines.append("")

    lines.append(colorize("Repository:", Style.BOLD))
    lines.append(f"    {colorize(repo, Style.GREEN)}")
    lines.append("")

    return "\n".join(lines)


def format_prepush_summary(
    branch: str,
    remote: str = "origin",
    commit_msg: Optional[str] = None,
    force: bool = False,
    tags: bool = False,
    diff_summary: Optional[Dict[str, Any]] = None,
    cwd: Optional[str] = None
) -> str:
    """
    Format rich pre-push preview:
    - Target branch & remote
    - Protected branch / detached HEAD warning
    - Ahead / Behind status
    - Files changed (+/- additions and deletions)
    - Commit message / pending commits
    """
    if diff_summary is None:
        diff_summary = get_diffstat_summary(cwd)

    repo_name = get_repo_name(cwd)
    repo_root = get_repo_root(cwd) or os.getcwd()
    detached = is_detached_head(cwd)
    is_prot = is_protected_branch(branch)
    behind, ahead = get_ahead_behind(remote, branch, cwd)

    lines = []
    lines.append("")
    lines.append(colorize("═══════════════════════════════════════════════════════════════", Style.CYAN))
    lines.append(colorize(" 🚀 GITPUSH PRE-PUSH INSPECTION & SUMMARY", Style.BOLD, Style.CYAN))
    lines.append(colorize("═══════════════════════════════════════════════════════════════", Style.CYAN))
    lines.append("")

    # Repository
    lines.append(f"{colorize('Repository:', Style.BOLD)}  {colorize(repo_name, Style.GREEN)} ({repo_root})")

    # Branch Status
    branch_display = branch
    if detached:
        branch_display = colorize(f"{branch} ⚠️ [DETACHED HEAD]", Style.BOLD, Style.RED)
    elif is_prot:
        branch_display = colorize(f"{branch} ⚠️ [PROTECTED BRANCH]", Style.BOLD, Style.YELLOW)
    else:
        branch_display = colorize(branch, Style.CYAN)

    lines.append(f"{colorize('Target Branch:', Style.BOLD)} {branch_display}  ──>  {colorize(f'{remote}/{branch}', Style.DIM)}")

    # Sync Status
    sync_parts = []
    if ahead > 0:
        sync_parts.append(colorize(f"Ahead: {ahead} commit(s)", Style.GREEN))
    if behind > 0:
        sync_parts.append(colorize(f"Behind: {behind} commit(s)", Style.RED))
    if ahead == 0 and behind == 0:
        sync_parts.append(colorize("In sync with remote", Style.DIM))
    lines.append(f"{colorize('Sync Status:', Style.BOLD)}   {', '.join(sync_parts)}")

    # Operation Mode / Flags
    flags_desc = []
    if force:
        flags_desc.append(colorize("--force-with-lease [SAFE FORCE]", Style.BOLD, Style.YELLOW))
    if tags:
        flags_desc.append(colorize("--tags", Style.MAGENTA))
    if commit_msg:
        flags_desc.append(f"Commit: {colorize(repr(commit_msg), Style.WHITE)}")
    else:
        flags_desc.append("Push existing commits/staged changes")
    lines.append(f"{colorize('Action:', Style.BOLD)}        {', '.join(flags_desc)}")

    # Critical Warnings
    warnings = []
    if detached:
        warnings.append("You are in a DETACHED HEAD state! Commits will not belong to any branch.")
    if is_prot and force:
        warnings.append(f"FORCE PUSHING to protected branch '{branch}'! Be extremely cautious.")
    elif is_prot and not force:
        warnings.append(f"Pushing directly to protected branch '{branch}'.")
    if behind > 0:
        warnings.append(f"Your branch is {behind} commit(s) behind '{remote}/{branch}'. A pull or rebase may be needed.")

    if warnings:
        lines.append("")
        lines.append(colorize("Warnings:", Style.BOLD, Style.YELLOW))
        for w in warnings:
            lines.append(f"  ⚠️  {colorize(w, Style.YELLOW)}")

    # Changed Files & Line Stats
    files = diff_summary["files"]
    tot_adds = diff_summary["total_additions"]
    tot_dels = diff_summary["total_deletions"]
    tot_files = diff_summary["modified_count"]

    lines.append("")
    if tot_files > 0:
        add_stat = colorize(f"+{tot_adds}", Style.GREEN)
        del_stat = colorize(f"-{tot_dels}", Style.RED)
        lines.append(colorize(f"Changed Files ({tot_files} file(s), {add_stat} / {del_stat}):", Style.BOLD))
        
        # Display up to 15 files
        display_limit = 15
        for f in files[:display_limit]:
            stat_code = f.status.ljust(2)
            if f.status == "??":
                stat_styled = colorize("??", Style.YELLOW)
            elif "M" in f.status:
                stat_styled = colorize(stat_code, Style.CYAN)
            elif "A" in f.status:
                stat_styled = colorize(stat_code, Style.GREEN)
            elif "D" in f.status:
                stat_styled = colorize(stat_code, Style.RED)
            else:
                stat_styled = stat_code
            
            lines.append(f"  {stat_styled}  {f.path.ljust(35)}  {f.diff_stat_str}")

        if len(files) > display_limit:
            lines.append(colorize(f"  ... and {len(files) - display_limit} more file(s)", Style.DIM))
    else:
        lines.append(colorize("Changed Files:", Style.BOLD) + " " + colorize("No uncommitted file changes (clean working tree)", Style.DIM))

    # Pending Commits to be pushed
    pending = get_pending_commits(remote, branch, cwd)
    if pending:
        lines.append("")
        lines.append(colorize(f"Pending Commits to Push ({len(pending)}):", Style.BOLD))
        for sha, subj in pending[:5]:
            lines.append(f"  • {colorize(sha, Style.YELLOW)} {subj}")
        if len(pending) > 5:
            lines.append(colorize(f"  • ... and {len(pending) - 5} more", Style.DIM))

    lines.append(colorize("═══════════════════════════════════════════════════════════════", Style.CYAN))
    lines.append("")
    return "\n".join(lines)


def prompt_confirm(prompt_text: str = "Continue? [y/N]: ", default: bool = False) -> bool:
    """
    Prompt user for interactive confirmation.
    Returns True if confirmed (y/Y/yes), False otherwise.
    """
    try:
        sys.stdout.write(colorize(prompt_text, Style.BOLD))
        sys.stdout.flush()
        response = input().strip().lower()
        if not response:
            return default
        return response in ("y", "yes")
    except (EOFError, KeyboardInterrupt):
        sys.stdout.write("\n")
        return False
