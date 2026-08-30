"""
GitPush Sync Engine
Intelligent single-command replacement for the pull → add → commit → push cycle.
Detects repository state and acts accordingly with interactive prompts.
"""

import sys
import subprocess
from typing import Optional, List

from .safety import (
    is_git_repo,
    get_repo_name,
    get_repo_root,
    get_current_branch,
    is_detached_head,
    is_protected_branch,
    get_ahead_behind,
    get_diffstat_summary,
    get_pending_commits,
    run_git,
    colorize,
    Style,
    prompt_confirm,
)


# ──────────────────────────────────────────────────────────────────
#  Helpers
# ──────────────────────────────────────────────────────────────────

def _fetch(remote: str = "origin", cwd: Optional[str] = None) -> bool:
    """Fetch from remote silently. Returns True on success."""
    print(f"\n{colorize('🔄 Fetching from remote...', Style.DIM)}")
    res = run_git(["fetch", remote], check=False, cwd=cwd)
    if res.returncode != 0:
        err = res.stderr.strip() if res.stderr else "unknown error"
        print(colorize(f"   ⚠️  Fetch failed: {err}", Style.YELLOW))
        return False
    return True


def _get_tracking_info(branch: str, cwd: Optional[str] = None) -> Optional[str]:
    """Return the upstream tracking ref (e.g. 'origin/main') or None."""
    res = run_git(["rev-parse", "--abbrev-ref", "--symbolic-full-name", f"{branch}@{{u}}"], cwd=cwd)
    if res.returncode == 0 and res.stdout.strip():
        return res.stdout.strip()
    return None


def _has_remote(remote: str = "origin", cwd: Optional[str] = None) -> bool:
    """Check if the named remote exists."""
    res = run_git(["remote", "get-url", remote], cwd=cwd)
    return res.returncode == 0


def _set_upstream_and_push(remote: str, branch: str, cwd: Optional[str] = None) -> bool:
    """Push current branch and set upstream tracking."""
    print(f"🚀 Pushing and setting upstream → {remote}/{branch}")
    try:
        subprocess.run(
            ["git", "push", "-u", remote, branch],
            check=True,
            cwd=cwd
        )
        print(colorize("✅ Upstream set and pushed successfully.", Style.GREEN))
        return True
    except subprocess.CalledProcessError as e:
        err = e.stderr.decode(errors="ignore").strip() if e.stderr else str(e)
        print(f"❌ Push failed: {err}", file=sys.stderr)
        return False


def _auto_generate_message(diff_summary: dict) -> str:
    """Generate a short commit message from the diff summary."""
    total = diff_summary["modified_count"]
    adds = diff_summary["total_additions"]
    dels = diff_summary["total_deletions"]
    parts = []
    if total == 1:
        parts.append(f"Update {diff_summary['files'][0].path}")
    else:
        parts.append(f"Update {total} files")
    parts.append(f"(+{adds}, -{dels})")
    return " ".join(parts)


def _stage_and_commit(message: str, cwd: Optional[str] = None) -> bool:
    """Stage all changes and commit."""
    try:
        subprocess.run(["git", "add", "."], check=True, capture_output=True, cwd=cwd)
        subprocess.run(
            ["git", "commit", "-m", message, "--allow-empty-message"],
            check=True,
            capture_output=True,
            cwd=cwd
        )
        return True
    except subprocess.CalledProcessError as e:
        err = e.stderr.decode(errors="ignore").strip() if e.stderr else str(e)
        if "nothing to commit" in err:
            print(colorize("ℹ️  Nothing to commit.", Style.DIM))
            return True
        print(f"❌ Commit failed: {err}", file=sys.stderr)
        return False


def _pull_ff(remote: str, branch: str, cwd: Optional[str] = None) -> bool:
    """Fast-forward pull."""
    print(f"⬇️  Pulling {remote}/{branch} (fast-forward)...")
    try:
        subprocess.run(
            ["git", "pull", "--ff-only", remote, branch],
            check=True,
            cwd=cwd
        )
        print(colorize("✅ Fast-forward pull complete.", Style.GREEN))
        return True
    except subprocess.CalledProcessError:
        print(colorize("⚠️  Fast-forward failed (branches may have diverged).", Style.YELLOW))
        return False


def _pull_merge(remote: str, branch: str, cwd: Optional[str] = None) -> bool:
    """Pull with merge strategy."""
    print(f"⬇️  Pulling {remote}/{branch} (merge)...")
    try:
        result = subprocess.run(
            ["git", "pull", remote, branch],
            capture_output=True, text=True,
            cwd=cwd
        )
        if result.returncode != 0:
            err = result.stderr.strip() if result.stderr else result.stdout.strip()
            if "CONFLICT" in err or "CONFLICT" in (result.stdout or ""):
                print(colorize("❗ Merge conflicts detected. Resolve them and run `gitpush sync` again.", Style.RED))
                _show_conflicts(cwd=cwd)
                return False
            print(f"❌ Merge pull failed: {err}", file=sys.stderr)
            return False

        if "CONFLICT" in (result.stdout or ""):
            print(colorize("❗ Merge conflicts detected. Resolve them and run `gitpush sync` again.", Style.RED))
            _show_conflicts(cwd=cwd)
            return False

        print(colorize("✅ Merge pull complete.", Style.GREEN))
        return True
    except subprocess.CalledProcessError as e:
        err = e.stderr.decode(errors="ignore").strip() if e.stderr else str(e)
        print(f"❌ Pull failed: {err}", file=sys.stderr)
        return False


def _pull_rebase(remote: str, branch: str, cwd: Optional[str] = None) -> bool:
    """Pull with rebase strategy."""
    print(f"🔁 Rebasing onto {remote}/{branch}...")
    try:
        result = subprocess.run(
            ["git", "pull", "--rebase", remote, branch],
            capture_output=True, text=True,
            cwd=cwd
        )
        if result.returncode != 0:
            err = result.stderr.strip() if result.stderr else result.stdout.strip()
            if "CONFLICT" in err or "CONFLICT" in (result.stdout or ""):
                print(colorize("❗ Rebase conflicts detected.", Style.RED))
                print("   Resolve conflicts, then run:")
                print(colorize("     git rebase --continue", Style.CYAN))
                print("   Or abort with:")
                print(colorize("     git rebase --abort", Style.CYAN))
                return False
            print(f"❌ Rebase failed: {err}", file=sys.stderr)
            return False
        print(colorize("✅ Rebase complete.", Style.GREEN))
        return True
    except subprocess.CalledProcessError as e:
        err = e.stderr.decode(errors="ignore").strip() if e.stderr else str(e)
        print(f"❌ Rebase failed: {err}", file=sys.stderr)
        return False


def _push(remote: str, branch: str, cwd: Optional[str] = None) -> bool:
    """Standard push."""
    print(f"🚀 Pushing to {remote}/{branch}...")
    try:
        subprocess.run(["git", "push", remote, branch], check=True, cwd=cwd)
        print(colorize("✅ Push complete.", Style.GREEN))
        return True
    except subprocess.CalledProcessError as e:
        err = e.stderr.decode(errors="ignore").strip() if e.stderr else str(e)
        print(f"❌ Push failed: {err}", file=sys.stderr)
        return False


def _show_conflicts(cwd: Optional[str] = None):
    """Print conflicted files."""
    res = run_git(["diff", "--name-only", "--diff-filter=U"], cwd=cwd)
    if res.returncode == 0 and res.stdout.strip():
        files = res.stdout.strip().splitlines()
        print(colorize(f"\n   Conflicted files ({len(files)}):", Style.BOLD))
        for f in files[:10]:
            print(f"     • {f}")
        if len(files) > 10:
            print(f"     • ... and {len(files) - 10} more")


def _prompt_choice(prompt_text: str, options: List[str]) -> int:
    """
    Display numbered options and prompt user to choose.
    Returns 0-based index, or -1 on cancel.
    """
    print()
    for i, opt in enumerate(options, 1):
        print(f"  {colorize(str(i), Style.BOLD, Style.CYAN)}. {opt}")
    print()
    try:
        sys.stdout.write(colorize(prompt_text, Style.BOLD))
        sys.stdout.flush()
        choice = input().strip()
        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(options):
                return idx
        return -1
    except (EOFError, KeyboardInterrupt):
        sys.stdout.write("\n")
        return -1


# ──────────────────────────────────────────────────────────────────
#  Sync Dashboard
# ──────────────────────────────────────────────────────────────────

def _print_sync_header(branch: str, remote: str, behind: int, ahead: int, diff_summary: dict, cwd: Optional[str] = None):
    """Print a compact sync status dashboard."""
    repo = get_repo_name(cwd)

    print()
    print(colorize("═══════════════════════════════════════════════════════════════", Style.CYAN))
    print(colorize(" 🔄 GITPUSH SYNC", Style.BOLD, Style.CYAN))
    print(colorize("═══════════════════════════════════════════════════════════════", Style.CYAN))
    print()

    print(f"  {colorize('Repository:', Style.BOLD)}  {colorize(repo, Style.GREEN)}")

    branch_display = branch
    if is_protected_branch(branch):
        branch_display = colorize(f"{branch} ⚠️ [PROTECTED]", Style.BOLD, Style.YELLOW)
    else:
        branch_display = colorize(branch, Style.CYAN)
    print(f"  {colorize('Branch:', Style.BOLD)}      {branch_display}  ↔  {colorize(f'{remote}/{branch}', Style.DIM)}")

    # Sync indicators
    local_label = f"{ahead} commit(s) ahead" if ahead > 0 else "0 commits ahead"
    remote_label = f"{behind} commit(s) ahead" if behind > 0 else "0 commits ahead"

    if ahead > 0:
        local_styled = colorize(local_label, Style.GREEN)
    else:
        local_styled = colorize(local_label, Style.DIM)

    if behind > 0:
        remote_styled = colorize(remote_label, Style.YELLOW)
    else:
        remote_styled = colorize(remote_label, Style.DIM)

    print(f"  {colorize('Local:', Style.BOLD)}       {local_styled}")
    print(f"  {colorize('Remote:', Style.BOLD)}      {remote_styled}")

    # Working tree
    if diff_summary["has_changes"]:
        n_files = diff_summary["modified_count"]
        adds = colorize(f"+{diff_summary['total_additions']}", Style.GREEN)
        dels = colorize(f"-{diff_summary['total_deletions']}", Style.RED)
        print(f"  {colorize('Working Tree:', Style.BOLD)} {colorize(f'{n_files} file(s) modified', Style.YELLOW)} ({adds}, {dels})")
    else:
        print(f"  {colorize('Working Tree:', Style.BOLD)} {colorize('Clean', Style.GREEN)}")

    print()


def _print_sync_footer(success: bool):
    """Print the sync result footer."""
    if success:
        print(colorize("═══════════════════════════════════════════════════════════════", Style.GREEN))
        print(colorize(" ✅ Sync complete!", Style.BOLD, Style.GREEN))
        print(colorize("═══════════════════════════════════════════════════════════════", Style.GREEN))
    else:
        print(colorize("═══════════════════════════════════════════════════════════════", Style.RED))
        print(colorize(" ❌ Sync incomplete — see errors above.", Style.BOLD, Style.RED))
        print(colorize("═══════════════════════════════════════════════════════════════", Style.RED))
    print()


# ──────────────────────────────────────────────────────────────────
#  Main Sync Flow
# ──────────────────────────────────────────────────────────────────

def run_sync_flow(
    auto_confirm: bool = False,
    commit_message: Optional[str] = None,
    prefer_rebase: bool = False,
    remote: str = "origin",
    cwd: Optional[str] = None,
) -> int:
    """
    Run the full sync flow:
      1. Validate repo state
      2. Fetch remote
      3. Detect scenario (clean, dirty, ahead, behind, diverged, no upstream)
      4. Execute appropriate actions with interactive prompts
      5. Report result

    Returns exit code: 0 for success, 1 for failure/abort.
    """

    # ── 1. Validate ──────────────────────────────────────────────
    if not is_git_repo(cwd):
        print("❌ Not a Git repository (or any of the parent directories).", file=sys.stderr)
        print("➡️  Run 'gitpush --init' or 'git init' first.", file=sys.stderr)
        return 1

    if is_detached_head(cwd):
        print(colorize("❌ Cannot sync in detached HEAD state.", Style.RED))
        print("➡️  Check out a branch first: git checkout <branch>")
        return 1

    branch = get_current_branch(cwd)

    # Protected branch warning
    if is_protected_branch(branch):
        print(colorize(f"\n⚠️  You are syncing on protected branch '{branch}'.", Style.BOLD, Style.YELLOW))
        if not auto_confirm:
            if not prompt_confirm("Continue? [y/N]: "):
                print(colorize("🛑 Sync cancelled.", Style.YELLOW))
                return 0

    # ── 2. Check remote & upstream ───────────────────────────────
    if not _has_remote(remote, cwd=cwd):
        print(colorize(f"❌ Remote '{remote}' does not exist.", Style.RED))
        print(f"➡️  Add one with: git remote add {remote} <url>")
        return 1

    tracking = _get_tracking_info(branch, cwd=cwd)
    no_upstream = tracking is None

    # ── 3. Fetch ─────────────────────────────────────────────────
    if not no_upstream:
        _fetch(remote, cwd=cwd)

    # ── 4. Detect state ──────────────────────────────────────────
    diff_summary = get_diffstat_summary(cwd=cwd)
    has_dirty = diff_summary["has_changes"]

    if no_upstream:
        behind, ahead = 0, 0
    else:
        behind, ahead = get_ahead_behind(remote, branch, cwd=cwd)

    # Print dashboard
    _print_sync_header(branch, remote, behind, ahead, diff_summary, cwd=cwd)

    # ── 5. Handle no-upstream scenario ───────────────────────────
    if no_upstream:
        print(colorize("ℹ️  No upstream tracking branch configured.", Style.YELLOW))

        # If dirty, commit first
        if has_dirty:
            print(colorize("   Modified files detected.", Style.YELLOW))
            if not auto_confirm:
                if not prompt_confirm("   Commit before pushing? [y/N]: "):
                    print(colorize("🛑 Sync cancelled.", Style.YELLOW))
                    return 0
            msg = commit_message or _auto_generate_message(diff_summary)
            print(f"\n📦 Committing: {colorize(repr(msg), Style.WHITE)}")
            if not _stage_and_commit(msg, cwd=cwd):
                _print_sync_footer(False)
                return 1

        if not auto_confirm:
            if not prompt_confirm(f"   Push and set upstream to {remote}/{branch}? [y/N]: "):
                print(colorize("🛑 Sync cancelled.", Style.YELLOW))
                return 0

        success = _set_upstream_and_push(remote, branch, cwd=cwd)
        _print_sync_footer(success)
        return 0 if success else 1

    # ── 6. Handle dirty working tree ─────────────────────────────
    if has_dirty:
        print(colorize("📝 Modified files detected.", Style.YELLOW))
        n_files = diff_summary["modified_count"]
        # Show first few changed files
        for f in diff_summary["files"][:8]:
            status_icon = {"M": "~", "A": "+", "D": "-", "??": "?"}.get(f.status, "·")
            print(f"     {colorize(status_icon, Style.CYAN)} {f.path}")
        if n_files > 8:
            print(colorize(f"     ... and {n_files - 8} more", Style.DIM))
        print()

        if not auto_confirm:
            if not prompt_confirm("   Commit before sync? [y/N]: "):
                print(colorize("⚠️  Skipping commit. Only existing commits will be synced.", Style.YELLOW))
            else:
                msg = commit_message
                if not msg:
                    try:
                        sys.stdout.write(colorize("   Commit message (Enter for auto): ", Style.BOLD))
                        sys.stdout.flush()
                        msg = input().strip()
                    except (EOFError, KeyboardInterrupt):
                        print()
                        msg = ""
                if not msg:
                    msg = _auto_generate_message(diff_summary)
                print(f"\n📦 Committing: {colorize(repr(msg), Style.WHITE)}")
                if not _stage_and_commit(msg, cwd=cwd):
                    _print_sync_footer(False)
                    return 1

                # Refresh ahead count after commit
                _, ahead = get_ahead_behind(remote, branch, cwd=cwd)
        else:
            # Auto mode: commit with provided or auto message
            msg = commit_message or _auto_generate_message(diff_summary)
            print(f"\n📦 Committing: {colorize(repr(msg), Style.WHITE)}")
            if not _stage_and_commit(msg, cwd=cwd):
                _print_sync_footer(False)
                return 1
            _, ahead = get_ahead_behind(remote, branch, cwd=cwd)

    # Re-check counts after potential commit
    behind, ahead = get_ahead_behind(remote, branch, cwd=cwd)

    # ── 7. Scenario: Synced ──────────────────────────────────────
    if behind == 0 and ahead == 0:
        print(colorize("✅ Already in sync — nothing to do.", Style.GREEN))
        _print_sync_footer(True)
        return 0

    # ── 8. Scenario: Local ahead only → push ─────────────────────
    if ahead > 0 and behind == 0:
        print(colorize(f"→ Safe to push ({ahead} commit(s) ahead, remote is up to date).", Style.GREEN))
        print()

        # Show pending commits
        pending = get_pending_commits(remote, branch, cwd=cwd)
        if pending:
            print(colorize(f"  Commits to push ({len(pending)}):", Style.BOLD))
            for sha, subj in pending[:5]:
                print(f"    • {colorize(sha, Style.YELLOW)} {subj}")
            if len(pending) > 5:
                print(colorize(f"    • ... and {len(pending) - 5} more", Style.DIM))
            print()

        if not auto_confirm:
            if not prompt_confirm("   Push now? [Y/n]: "):
                print(colorize("🛑 Push cancelled.", Style.YELLOW))
                return 0

        success = _push(remote, branch, cwd=cwd)
        _print_sync_footer(success)
        return 0 if success else 1

    # ── 9. Scenario: Remote ahead only → pull ────────────────────
    if behind > 0 and ahead == 0:
        print(colorize(f"→ Remote is {behind} commit(s) ahead. Pulling...", Style.YELLOW))
        print()

        success = _pull_ff(remote, branch, cwd=cwd)
        if not success:
            # Fast-forward failed, try regular pull
            success = _pull_merge(remote, branch, cwd=cwd)

        _print_sync_footer(success)
        return 0 if success else 1

    # ── 10. Scenario: Diverged ───────────────────────────────────
    if behind > 0 and ahead > 0:
        print(colorize(f"⚠️  Branch has diverged.", Style.BOLD, Style.YELLOW))
        print(f"     Local:  {colorize(f'{ahead} commit(s) ahead', Style.GREEN)}")
        print(f"     Remote: {colorize(f'{behind} commit(s) ahead', Style.YELLOW)}")
        print()

        if prefer_rebase or auto_confirm:
            # Auto mode or --rebase flag → rebase
            strategy = "rebase"
        else:
            choice = _prompt_choice(
                "Choose strategy [1/2/3]: ",
                [
                    colorize("Rebase", Style.GREEN) + " — replay your commits on top of remote (clean history)",
                    colorize("Merge", Style.CYAN) + "  — merge remote into local (preserves history)",
                    colorize("Abort", Style.RED) + "   — cancel sync",
                ]
            )
            if choice == 0:
                strategy = "rebase"
            elif choice == 1:
                strategy = "merge"
            else:
                print(colorize("\n🛑 Sync aborted.", Style.YELLOW))
                return 0

        if strategy == "rebase":
            success = _pull_rebase(remote, branch, cwd=cwd)
        else:
            success = _pull_merge(remote, branch, cwd=cwd)

        if not success:
            _print_sync_footer(False)
            return 1

        # After successful rebase/merge, push
        print()
        success = _push(remote, branch, cwd=cwd)
        _print_sync_footer(success)
        return 0 if success else 1

    # ── Fallback (shouldn't reach here) ──────────────────────────
    print(colorize("ℹ️  Could not determine sync state.", Style.DIM))
    _print_sync_footer(False)
    return 1
