"""
GitPush Undo Engine
Intelligent, context-aware Git undo manager capable of handling unpushed/pushed commits,
working tree preservation, merge commits, protected branches, and remote rollback.
"""

import os
import sys
import subprocess
from typing import Optional, List, Dict, Tuple, Any

from .safety import (
    is_git_repo,
    get_repo_name,
    get_repo_root,
    get_current_branch,
    is_detached_head,
    is_protected_branch,
    get_ahead_behind,
    get_diffstat_summary,
    prompt_confirm,
    run_git,
    colorize,
    Style
)


def get_commit_info(ref: str = "HEAD", cwd: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Get commit hash, short hash, subject, author, and parents for a ref."""
    res = run_git(["log", "-1", "--format=%H%x00%h%x00%s%x00%an%x00%P", ref], cwd=cwd)
    if res.returncode != 0 or not res.stdout.strip():
        return None
    parts = res.stdout.strip().split("\x00")
    if len(parts) < 5:
        return None
    full_sha, short_sha, subject, author, parents_str = parts[0], parts[1], parts[2], parts[3], parts[4]
    parents = parents_str.split() if parents_str.strip() else []
    return {
        "full_sha": full_sha,
        "short_sha": short_sha,
        "subject": subject,
        "author": author,
        "parents": parents,
        "is_merge": len(parents) > 1
    }


def is_commit_pushed(commit_sha: str, remote: str = "origin", branch: Optional[str] = None, cwd: Optional[str] = None) -> bool:
    """Check if a commit exists on the remote tracking branch."""
    if not branch:
        branch = get_current_branch(cwd)
    
    # Check if remote branch exists
    res = run_git(["rev-parse", "--verify", f"{remote}/{branch}"], cwd=cwd)
    if res.returncode != 0:
        return False
    
    # Check if commit_sha is an ancestor of remote/branch
    res_anc = run_git(["merge-base", "--is-ancestor", commit_sha, f"{remote}/{branch}"], cwd=cwd)
    return res_anc.returncode == 0


def get_recent_git_actions(count: int = 5, cwd: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Get a list of recent Git actions from log and reflog for interactive undo selection.
    """
    actions = []
    
    # Fetch recent commits
    res = run_git(["log", f"-n{count}", "--format=%H%x00%h%x00%s%x00%an%x00%cr%x00%P"], cwd=cwd)
    if res.returncode == 0 and res.stdout.strip():
        for line in res.stdout.strip().splitlines():
            parts = line.split("\x00")
            if len(parts) >= 5:
                sha, short_sha, subject, author, rel_date = parts[0], parts[1], parts[2], parts[3], parts[4]
                parents = parts[5].split() if len(parts) > 5 and parts[5] else []
                is_pushed = is_commit_pushed(sha, cwd=cwd)
                actions.append({
                    "type": "commit",
                    "full_sha": sha,
                    "short_sha": short_sha,
                    "subject": subject,
                    "author": author,
                    "rel_date": rel_date,
                    "is_merge": len(parents) > 1,
                    "is_pushed": is_pushed
                })

    return actions


def format_recent_actions_menu(actions: List[Dict[str, Any]]) -> str:
    """Format recent git actions for user selection."""
    lines = []
    lines.append("")
    lines.append(colorize("Recent Git actions", Style.BOLD))
    lines.append(colorize("────────────────────────────────────────────────────────", Style.DIM))
    
    for idx, act in enumerate(actions, 1):
        short_sha = colorize(act['short_sha'], Style.YELLOW)
        subject = act['subject']
        if len(subject) > 50:
            subject = subject[:47] + "..."
        
        status_tag = ""
        if act['is_pushed']:
            status_tag = colorize("[Pushed to remote]", Style.CYAN)
        else:
            status_tag = colorize("[Local only]", Style.GREEN)
        
        if act['is_merge']:
            status_tag += " " + colorize("[Merge Commit]", Style.MAGENTA)
            
        lines.append(f"  {colorize(str(idx) + '.', Style.BOLD)} Commit: {short_sha} {subject} {status_tag} {colorize('(' + act['rel_date'] + ')', Style.DIM)}")

    lines.append("")
    return "\n".join(lines)


def undo_commit(
    target_sha: Optional[str] = None,
    mode: str = "soft", # "soft" (keep changes staged/working), "mixed" (unstage), "hard" (discard)
    auto_confirm: bool = False,
    cwd: Optional[str] = None
) -> bool:
    """
    Undo the last commit (or specified commit) with full safety and context awareness.
    """
    if not is_git_repo(cwd):
        print(colorize("❌ Not a Git repository.", Style.RED))
        return False

    current_branch = get_current_branch(cwd)
    commit = get_commit_info(target_sha or "HEAD", cwd=cwd)
    if not commit:
        print(colorize("❌ No commits found to undo.", Style.YELLOW))
        return False

    is_pushed = is_commit_pushed(commit["full_sha"], branch=current_branch, cwd=cwd)
    is_prot = is_protected_branch(current_branch)
    diff_info = get_diffstat_summary(cwd)
    has_dirty_worktree = diff_info["has_changes"]

    print("")
    print(colorize("═══════════════════════════════════════════════════════════════", Style.CYAN))
    print(colorize(" ⏪ GITPUSH UNDO INSPECTION", Style.BOLD, Style.CYAN))
    print(colorize("═══════════════════════════════════════════════════════════════", Style.CYAN))
    print("")
    print(f"{colorize('Target Action:', Style.BOLD)}  Commit {colorize(commit['short_sha'], Style.YELLOW)}: {commit['subject']}")
    print(f"{colorize('Branch:', Style.BOLD)}         {colorize(current_branch, Style.CYAN)}")
    
    if is_pushed:
        print(f"{colorize('Status:', Style.BOLD)}         {colorize('PUSHED to remote repository ⚠️', Style.BOLD, Style.YELLOW)}")
    else:
        print(f"{colorize('Status:', Style.BOLD)}         {colorize('Local only (Unpushed) ✔', Style.GREEN)}")

    if commit["is_merge"]:
        print(f"{colorize('Type:', Style.BOLD)}           {colorize('Merge Commit (2+ parents) ⚠️', Style.MAGENTA)}")

    print("")
    print(colorize("This will:", Style.BOLD))
    if is_pushed:
        if is_prot:
            print(colorize("  ⚠️  WARNING: Target is a PROTECTED branch ('" + current_branch + "').", Style.BOLD, Style.YELLOW))
            print("  ✓ Rewind HEAD locally and keep all your file changes")
            print("  ⚠️  Require a safe force-push (--force-with-lease) OR a revert to sync remote")
        else:
            print("  ✓ Keep all your file changes intact in your working directory")
            print("  ✗ Remove the commit from your local branch history")
            print("  ⚠️  Require a force-push (`gitpush --force`) if you want to update the remote")
    else:
        print(colorize("  ✓ Keep all your file changes in your working tree", Style.GREEN))
        print(colorize("  ✗ Remove the commit from local history cleanly", Style.YELLOW))

    if has_dirty_worktree:
        print(colorize(f"\nℹ Note: You have {diff_info['modified_count']} uncommitted file changes. They will be safely preserved.", Style.CYAN))

    print(colorize(f"\n💡 Recovery tip: If needed, you can restore this commit later with: git reset --hard {commit['short_sha']}", Style.DIM))
    print(colorize("═══════════════════════════════════════════════════════════════", Style.CYAN))
    print("")

    if not auto_confirm:
        if not prompt_confirm("Continue? [y/N]: "):
            print(colorize("\n🛑 Undo cancelled by user.", Style.YELLOW))
            return False

    # Execute soft reset
    try:
        reset_flag = "--soft" if mode == "soft" else "--mixed"
        res = run_git(["reset", reset_flag, "HEAD~1"], cwd=cwd)
        if res.returncode == 0:
            print(colorize(f"\n✅ Successfully rewound commit {commit['short_sha']}!", Style.BOLD, Style.GREEN))
            print("📁 All changes are now preserved in your working directory.")
            
            if is_pushed:
                print(colorize("\n⚡ Since this commit was already on remote, next steps:", Style.BOLD))
                push_example = colorize('gitpush "New message" --force', Style.CYAN)
                print(f"   • To make new changes & safe force-push: {push_example}")
                revert_cmd = f"git revert {commit['short_sha']}"
                print(f"   • To revert remote instead of force-pushing: {colorize(revert_cmd, Style.CYAN)}")
            else:
                commit_example = colorize('gitpush "New commit message"', Style.CYAN)
                print(f"   • When ready to recommit: {commit_example}")
            return True
        else:
            print(colorize(f"❌ Failed to reset commit: {res.stderr.strip()}", Style.RED), file=sys.stderr)
            return False
    except Exception as e:
        print(colorize(f"❌ Error during undo: {str(e)}", Style.RED), file=sys.stderr)
        return False


def undo_push(
    remote: str = "origin",
    branch: Optional[str] = None,
    auto_confirm: bool = False,
    cwd: Optional[str] = None
) -> bool:
    """
    Undo the last push by rolling back the remote tracking branch safely with --force-with-lease.
    """
    if not is_git_repo(cwd):
        print(colorize("❌ Not a Git repository.", Style.RED))
        return False

    current_branch = branch or get_current_branch(cwd)
    is_prot = is_protected_branch(current_branch)

    # Check ahead/behind
    behind, ahead = get_ahead_behind(remote, current_branch, cwd)

    commit = get_commit_info("HEAD", cwd=cwd)
    if not commit:
        print(colorize("❌ No commits found to inspect.", Style.YELLOW))
        return False

    print("")
    print(colorize("═══════════════════════════════════════════════════════════════", Style.CYAN))
    print(colorize(" ⏪ GITPUSH UNDO PUSH INSPECTION", Style.BOLD, Style.CYAN))
    print(colorize("═══════════════════════════════════════════════════════════════", Style.CYAN))
    print("")
    print(f"{colorize('Target Remote:', Style.BOLD)}  {remote}/{current_branch}")
    print(f"{colorize('Latest Commit:', Style.BOLD)}  {commit['short_sha']}: {commit['subject']}")

    if is_prot:
        print(colorize(f"\n🛑 CRITICAL WARNING: '{current_branch}' is a PROTECTED BRANCH!", Style.BOLD, Style.RED))
        print("   Rewinding a pushed commit on a shared/production branch can break collaborators' workflows.")
        revert_tip = f"git revert {commit['short_sha']}"
        print(f"   A safe alternative is to create a revert commit: {colorize(revert_tip, Style.CYAN)}")

    print("")
    print(colorize("This will:", Style.BOLD))
    print("  1. Rewind local HEAD by 1 commit (keeping all changes in working tree)")
    print(f"  2. Safe force-push (--force-with-lease) to rollback {remote}/{current_branch}")
    print("═══════════════════════════════════════════════════════════════")
    print("")

    if not auto_confirm:
        if not prompt_confirm(f"Are you sure you want to rollback {remote}/{current_branch}? [y/N]: "):
            print(colorize("\n🛑 Undo push cancelled by user.", Style.YELLOW))
            return False

    # Step 1: Soft reset locally
    print("\n📦 Rewinding local commit...")
    res_reset = run_git(["reset", "--soft", "HEAD~1"], cwd=cwd)
    if res_reset.returncode != 0:
        print(colorize(f"❌ Failed to reset local commit: {res_reset.stderr.strip()}", Style.RED))
        return False

    # Step 2: Force-with-lease push
    print(f"🚀 Updating remote {remote}/{current_branch} with --force-with-lease...")
    res_push = run_git(["push", remote, current_branch, "--force-with-lease"], cwd=cwd)
    if res_push.returncode == 0:
        print(colorize(f"\n✅ Successfully rolled back push on {remote}/{current_branch}!", Style.BOLD, Style.GREEN))
        print("📁 Your uncommitted changes are safely kept in your local workspace.")
        return True
    else:
        print(colorize(f"❌ Remote push failed: {res_push.stderr.strip()}", Style.RED))
        print("💡 Your local workspace was rewound to working changes.")
        return False


def run_undo_flow(args: List[str]) -> int:
    """
    Main router for `gitpush undo [subcommand]`
    """
    auto_confirm = ("-y" in args or "--yes" in args)
    clean_args = [a for a in args if a not in ("-y", "--yes")]

    subcommand = clean_args[0].lower() if clean_args else None

    # 1. gitpush undo push
    if subcommand == "push":
        remote = "origin"
        branch = None
        if len(clean_args) > 1:
            remote = clean_args[1]
        if len(clean_args) > 2:
            branch = clean_args[2]
        return 0 if undo_push(remote=remote, branch=branch, auto_confirm=auto_confirm) else 1

    # 2. gitpush undo commit / last
    if subcommand in ("commit", "last"):
        return 0 if undo_commit(auto_confirm=auto_confirm) else 1

    # 3. Context-aware or interactive menu when run simply as `gitpush undo`
    actions = get_recent_git_actions(count=5)
    if not actions:
        print(colorize("❌ No recent Git commits found to undo.", Style.YELLOW))
        return 1

    # If only 1 commit or called with auto_confirm, undo last commit directly
    if len(actions) == 1 or auto_confirm:
        return 0 if undo_commit(auto_confirm=auto_confirm) else 1

    # Interactive menu
    print(format_recent_actions_menu(actions))
    try:
        sys.stdout.write(colorize("What do you want to undo? (Enter number 1-5, or 'q' to quit): ", Style.BOLD))
        sys.stdout.flush()
        choice = input().strip()
        if choice.lower() in ("q", "quit", "exit", "n", "no", ""):
            print(colorize("\n🛑 Cancelled.", Style.YELLOW))
            return 0

        if not choice.isdigit() or int(choice) < 1 or int(choice) > len(actions):
            print(colorize(f"❌ Invalid selection: '{choice}'", Style.RED))
            return 1

        selected_action = actions[int(choice) - 1]
        if int(choice) == 1:
            return 0 if undo_commit(auto_confirm=False) else 1
        else:
            # Undoing an older commit requires soft reset to that commit's parent or revert
            print(f"\nSelected: Commit {selected_action['short_sha']} ({selected_action['subject']})")
            if selected_action["is_pushed"]:
                print(colorize("💡 This is an older pushed commit. Creating a safe revert commit is recommended.", Style.CYAN))
                if prompt_confirm(f"Revert commit {selected_action['short_sha']} with git revert? [Y/n]: ", default=True):
                    res = run_git(["revert", "--no-edit", selected_action["full_sha"]])
                    if res.returncode == 0:
                        print(colorize(f"✅ Revert commit created for {selected_action['short_sha']}. Ready to push with 'gitpush'.", Style.GREEN))
                        return 0
                    else:
                        print(colorize(f"❌ Revert failed: {res.stderr.strip()}", Style.RED))
                        return 1
            else:
                # Local commit: ask if rewind to before this commit
                if prompt_confirm(f"Rewind local branch to before commit {selected_action['short_sha']} (soft reset)? [y/N]: "):
                    res = run_git(["reset", "--soft", f"{selected_action['full_sha']}~1"])
                    if res.returncode == 0:
                        print(colorize(f"✅ Rewound to before {selected_action['short_sha']}. Changes kept in worktree.", Style.GREEN))
                        return 0
                    else:
                        print(colorize(f"❌ Reset failed: {res.stderr.strip()}", Style.RED))
                        return 1

        return 0

    except (EOFError, KeyboardInterrupt):
        print(colorize("\n🛑 Cancelled.", Style.YELLOW))
        return 0
