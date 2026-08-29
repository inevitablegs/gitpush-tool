"""
GitPush Decision-Support Status Dashboard
Provides a rich, actionable overview of repository health, worktree breakdown,
commit sync state, and intelligent contextual recommendations.
"""

import os
import sys
import subprocess
from typing import Optional, Dict, List, Tuple, Any

from .safety import (
    is_git_repo,
    get_repo_name,
    get_repo_root,
    get_current_branch,
    is_detached_head,
    is_protected_branch,
    get_ahead_behind,
    get_diffstat_summary,
    run_git,
    colorize,
    Style
)


def get_tracking_branch(cwd: Optional[str] = None) -> Optional[str]:
    """Get the upstream tracking branch for the current HEAD, e.g. origin/main."""
    res = run_git(["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"], cwd=cwd)
    if res.returncode == 0 and res.stdout.strip():
        return res.stdout.strip()
    return None


def get_stash_count(cwd: Optional[str] = None) -> int:
    """Get count of stashes in the stash list."""
    res = run_git(["stash", "list"], cwd=cwd)
    if res.returncode == 0 and res.stdout.strip():
        return len(res.stdout.strip().splitlines())
    return 0


def get_worktree_breakdown(cwd: Optional[str] = None) -> Dict[str, int]:
    """
    Categorizes working tree changes into:
    - modified
    - added (staged new files)
    - deleted
    - untracked
    - renamed
    - unmerged (conflicts)
    """
    counts = {
        "modified": 0,
        "added": 0,
        "deleted": 0,
        "untracked": 0,
        "renamed": 0,
        "unmerged": 0
    }
    
    res = run_git(["status", "--porcelain=v1", "-uall"], cwd=cwd)
    if res.returncode != 0 or not res.stdout.strip():
        return counts

    for line in res.stdout.splitlines():
        if len(line) < 3:
            continue
        index_code = line[0]
        work_code = line[1]
        
        # Check unmerged / conflicts
        if index_code in ('U', 'A', 'D') and work_code == 'U' or (index_code == 'U' and work_code in ('U', 'A', 'D')) or (index_code == 'A' and work_code == 'A') or (index_code == 'D' and work_code == 'D'):
            counts["unmerged"] += 1
            continue

        # Untracked
        if index_code == '?' and work_code == '?':
            counts["untracked"] += 1
            continue

        # Added / New in index
        if index_code == 'A':
            counts["added"] += 1
            if work_code == 'M':
                counts["modified"] += 1
            elif work_code == 'D':
                counts["deleted"] += 1
            continue

        # Deleted
        if index_code == 'D' or work_code == 'D':
            counts["deleted"] += 1
            continue

        # Renamed
        if index_code == 'R' or work_code == 'R':
            counts["renamed"] += 1
            continue

        # Modified
        if index_code == 'M' or work_code == 'M':
            counts["modified"] += 1
            continue

    return counts


def calculate_repo_health(
    detached: bool,
    unmerged_count: int,
    behind_count: int,
    diverged: bool,
    modified_count: int,
    untracked_count: int,
    stash_count: int,
    is_protected: bool
) -> Tuple[int, str, str]:
    """
    Computes a repository health score between 0 and 100 with a label and color style.
    Returns: (score, label, color_style)
    """
    score = 100

    # Severe issues
    if unmerged_count > 0:
        score -= min(40, unmerged_count * 20)
    if detached:
        score -= 25
    if diverged:
        score -= 20
    elif behind_count > 0:
        score -= min(15, behind_count * 3)

    # Worktree hygiene
    total_dirty = modified_count + untracked_count
    if total_dirty > 20:
        score -= 15
    elif total_dirty > 10:
        score -= 10
    elif total_dirty > 5:
        score -= 5

    # Stash buildup
    if stash_count > 10:
        score -= 10
    elif stash_count > 5:
        score -= 5

    # Clamp between 0 and 100
    score = max(0, min(100, score))

    if score >= 90:
        label = "Excellent (Clean & Ready)"
        color = Style.GREEN
    elif score >= 75:
        label = "Good (Minor Action Needed)"
        color = Style.CYAN
    elif score >= 50:
        label = "Attention Needed"
        color = Style.YELLOW
    else:
        label = "Critical (Conflicts / Detached)"
        color = Style.RED

    return score, label, color


def get_decision_recommendations(
    branch: str,
    tracking: Optional[str],
    ahead: int,
    behind: int,
    diverged: bool,
    detached: bool,
    worktree: Dict[str, int],
    is_protected: bool
) -> Tuple[List[str], List[str]]:
    """
    Generates actionable, contextual push/pull notes and recommended next commands.
    Returns: (status_notes, recommended_commands)
    """
    status_notes = []
    recommended = []

    total_worktree_changes = sum(worktree.values())

    # 1. Unmerged / Conflicts
    if worktree.get("unmerged", 0) > 0:
        status_notes.append(colorize(f"❌ {worktree['unmerged']} merge conflict(s) require resolution.", Style.BOLD, Style.RED))
        recommended.append("Resolve conflict markers in affected files, then run: git add .")
        recommended.append("Continue rebase/merge with: git rebase --continue (or git commit)")
        return status_notes, recommended

    # 2. Detached HEAD
    if detached:
        status_notes.append(colorize("⚠ You are in a detached HEAD state. Commits made here are not on a branch.", Style.YELLOW))
        recommended.append("Create a new branch to keep your work: git switch -c feature/my-new-branch")
        return status_notes, recommended

    # 3. Remote Tracking & Sync
    if tracking is None:
        status_notes.append("Branch has no remote tracking branch set.")
        if total_worktree_changes > 0:
            recommended.append(f'gitpush "Commit message" {branch} origin')
        else:
            recommended.append(f"git push -u origin {branch}")
    elif diverged:
        status_notes.append(colorize(f"⚠ Branch has diverged from '{tracking}' ({ahead} ahead, {behind} behind).", Style.YELLOW))
        recommended.append("Rebase onto remote changes: git pull --rebase")
        recommended.append(f'Then push your changes: gitpush')
    elif behind > 0:
        status_notes.append(colorize(f"⚠ Remote has {behind} commit(s) you don't have locally.", Style.YELLOW))
        recommended.append("git pull --rebase")
        if ahead > 0 or total_worktree_changes > 0:
            recommended.append(f'gitpush "Commit message"')
    elif ahead > 0:
        if total_worktree_changes > 0:
            status_notes.append(f"Ready to commit {total_worktree_changes} change(s) and push {ahead} commit(s).")
            recommended.append(f'gitpush "Commit message"')
        else:
            status_notes.append(colorize(f"✔ Ready to push {ahead} local commit(s) to '{tracking}'.", Style.GREEN))
            recommended.append("gitpush")
    else:
        # Synced with remote
        if total_worktree_changes > 0:
            status_notes.append(f"You have {total_worktree_changes} uncommitted file change(s).")
            recommended.append(f'gitpush "Describe your changes"')
        else:
            status_notes.append(colorize("✔ Repository is clean and in sync with remote.", Style.GREEN))
            recommended.append("No action needed (all changes committed and pushed).")

    # Protected branch advice
    if is_protected and (ahead > 0 or total_worktree_changes > 0):
        status_notes.append(colorize(f"ℹ '{branch}' is a protected branch.", Style.CYAN))
        if not any("git switch -c" in r for r in recommended):
            recommended.append(f"Tip: If contributing a feature, branch off: git switch -c feature/new-idea")

    return status_notes, recommended


def format_status_dashboard(cwd: Optional[str] = None, verbose: bool = False) -> str:
    """
    Format the complete decision-support status dashboard.
    """
    if not is_git_repo(cwd):
        return colorize("❌ Not a Git repository (or any of the parent directories).", Style.RED)

    repo_name = get_repo_name(cwd)
    branch = get_current_branch(cwd)
    detached = is_detached_head(cwd)
    tracking = get_tracking_branch(cwd)
    is_prot = is_protected_branch(branch)
    
    # Remote sync status
    remote = "origin"
    remote_branch = branch
    if tracking and "/" in tracking:
        remote, remote_branch = tracking.split("/", 1)
    
    behind, ahead = get_ahead_behind(remote, remote_branch, cwd)
    diverged = (ahead > 0 and behind > 0)
    
    # Worktree breakdown
    worktree = get_worktree_breakdown(cwd)
    stash_count = get_stash_count(cwd)
    diff_summary = get_diffstat_summary(cwd)
    
    # Health score
    score, health_label, health_color = calculate_repo_health(
        detached=detached,
        unmerged_count=worktree.get("unmerged", 0),
        behind_count=behind,
        diverged=diverged,
        modified_count=worktree["modified"],
        untracked_count=worktree["untracked"],
        stash_count=stash_count,
        is_protected=is_prot
    )

    # Decision recommendations
    status_notes, recommendations = get_decision_recommendations(
        branch=branch,
        tracking=tracking,
        ahead=ahead,
        behind=behind,
        diverged=diverged,
        detached=detached,
        worktree=worktree,
        is_protected=is_prot
    )

    lines = []
    lines.append("")
    lines.append(f"{colorize('Repository:', Style.BOLD)}  {colorize(repo_name, Style.GREEN)}")
    
    branch_styled = branch
    if detached:
        branch_styled = colorize(f"{branch} [DETACHED HEAD ⚠️]", Style.BOLD, Style.RED)
    elif is_prot:
        branch_styled = colorize(f"{branch} [Protected]", Style.BOLD, Style.YELLOW)
    else:
        branch_styled = colorize(branch, Style.CYAN)
    
    lines.append(f"{colorize('Branch:', Style.BOLD)}      {branch_styled}")
    tracking_str = tracking if tracking else colorize("None (no tracking remote)", Style.DIM)
    lines.append(f"{colorize('Tracking:', Style.BOLD)}    {tracking_str}")
    lines.append("")

    # WORKTREE section
    lines.append(colorize("WORKTREE", Style.BOLD))
    lines.append(colorize("────────────────────────", Style.DIM))
    total_worktree = sum(worktree.values())
    if total_worktree == 0:
        lines.append(colorize("Clean (no changes)", Style.DIM))
    else:
        if worktree["modified"] > 0:
            lines.append(f"Modified       {colorize(str(worktree['modified']), Style.CYAN)}")
        if worktree["added"] > 0:
            lines.append(f"Added          {colorize(str(worktree['added']), Style.GREEN)}")
        if worktree["deleted"] > 0:
            lines.append(f"Deleted        {colorize(str(worktree['deleted']), Style.RED)}")
        if worktree["renamed"] > 0:
            lines.append(f"Renamed        {colorize(str(worktree['renamed']), Style.CYAN)}")
        if worktree["untracked"] > 0:
            lines.append(f"Untracked      {colorize(str(worktree['untracked']), Style.YELLOW)}")
        if worktree["unmerged"] > 0:
            lines.append(f"Conflicts      {colorize(str(worktree['unmerged']), Style.BOLD, Style.RED)}")
        
        # Line stat addition/deletion
        if diff_summary["total_additions"] > 0 or diff_summary["total_deletions"] > 0:
            adds = colorize(f"+{diff_summary['total_additions']}", Style.GREEN)
            dels = colorize(f"-{diff_summary['total_deletions']}", Style.RED)
            lines.append(f"Line Changes   {adds}, {dels}")

    if stash_count > 0:
        lines.append(f"Stashes        {stash_count} saved")
    lines.append("")

    # COMMITS section
    lines.append(colorize("COMMITS", Style.BOLD))
    lines.append(colorize("────────────────────────", Style.DIM))
    ahead_str = colorize(str(ahead), Style.GREEN) if ahead > 0 else "0"
    behind_str = colorize(str(behind), Style.RED) if behind > 0 else "0"
    lines.append(f"Ahead          {ahead_str}")
    lines.append(f"Behind         {behind_str}")
    lines.append("")

    # PUSH / PULL section (Decision Support)
    lines.append(colorize("PUSH / STATUS", Style.BOLD))
    lines.append(colorize("────────────────────────", Style.DIM))
    for note in status_notes:
        lines.append(note)
    lines.append("")

    # Recommended Action
    lines.append(colorize("Recommended:", Style.BOLD))
    for rec in recommendations:
        lines.append(f"    {colorize(rec, Style.CYAN)}")
    lines.append("")

    # Repository Health Score
    health_bar_filled = int(score / 10)
    health_bar = f"[{'█' * health_bar_filled}{'░' * (10 - health_bar_filled)}]"
    lines.append(colorize("Health:", Style.BOLD))
    lines.append(f"    {colorize(f'{score}/100', Style.BOLD, health_color)} {colorize(health_bar, health_color)} {colorize(health_label, Style.DIM)}")
    lines.append("")

    return "\n".join(lines)
