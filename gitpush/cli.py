"""
GitPush CLI
A supercharged Git CLI tool that simplifies repository creation and pushing
with intelligent defaults, diffstat change summaries, and safety guards against dangerous Git actions.
"""

import os
import argparse
import sys
import subprocess
import shutil
import platform
import json
import tempfile
import urllib.request
from typing import Optional, List

# Reconfigure stdout/stderr encoding if possible for Windows console emoji support
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
    DangerousOperationAnalyzer,
    format_danger_box,
    format_prepush_summary,
    prompt_confirm,
    colorize,
    Style
)

from .status import format_status_dashboard


# --- GitHub CLI Installation Orchestrator and Helpers ---

def check_gh_installed() -> bool:
    """Check if GitHub CLI is installed with proper verification."""
    if shutil.which("gh"):
        try:
            subprocess.run(["gh", "--version"], check=True, capture_output=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False
    return False


def install_gh_cli() -> bool:
    """Main installation function with comprehensive error handling."""
    system = platform.system()
    machine = platform.machine().lower()
    
    print("\n🔧 Installing GitHub CLI...")
    print(f"📋 System: {system}, Architecture: {machine}")
    
    try:
        if system == "Windows":
            return install_gh_cli_windows()
        elif system == "Darwin":
            return install_gh_cli_mac()
        elif system == "Linux":
            return install_gh_cli_linux()
        else:
            print(f"❌ Unsupported OS: {system}")
            return False
    except Exception as e:
        print(f"❌ Installation failed: {str(e)}")
        return False


def install_gh_cli_windows() -> bool:
    """Windows installation with multiple fallback methods and PATH management."""
    methods = [
        try_winget_install,
        try_scoop_install,
        try_choco_install,
        try_direct_msi_install,
        try_direct_zip_install
    ]
    
    for method in methods:
        if method():
            if verify_gh_installation():
                return True
        print("   ⚠️ Trying next installation method...")
    
    print("❌ All Windows installation methods failed.")
    return False


def try_winget_install() -> bool:
    """Attempt installation via winget."""
    if not shutil.which("winget"):
        return False
    
    print("\n   🔄 Attempting winget installation...")
    try:
        subprocess.run(
            ["winget", "install", "--id", "GitHub.cli", "--silent", "--accept-package-agreements", "--accept-source-agreements"],
            check=True,
            capture_output=True
        )
        return True
    except subprocess.CalledProcessError as e:
        print(f"   ⚠️ winget failed: {e.stderr.decode(errors='ignore').strip() if e.stderr else 'Unknown error'}")
        return False


def try_scoop_install() -> bool:
    """Attempt installation via scoop."""
    if not shutil.which("scoop"):
        return False
    
    print("\n   🔄 Attempting scoop installation...")
    try:
        subprocess.run(["scoop", "install", "gh"], check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"   ⚠️ scoop failed: {e.stderr.decode(errors='ignore').strip() if e.stderr else 'Unknown error'}")
        return False


def try_choco_install() -> bool:
    """Attempt installation via chocolatey."""
    if not shutil.which("choco"):
        return False
    
    print("\n   🔄 Attempting chocolatey installation...")
    try:
        subprocess.run(["choco", "install", "gh", "-y"], check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"   ⚠️ chocolatey failed: {e.stderr.decode(errors='ignore').strip() if e.stderr else 'Unknown error'}")
        return False


def try_direct_msi_install() -> bool:
    """Direct MSI installation with proper PATH handling."""
    print("\n   🔄 Attempting direct MSI installation...")
    temp_dir = ""
    try:
        release_info = get_github_release_info()
        if not release_info:
            return False
        
        msi_asset = next((a for a in release_info.get('assets', []) if a['name'].endswith('_windows_amd64.msi')), None)
        if not msi_asset:
            print("   ❌ Could not find Windows MSI installer.")
            return False
            
        temp_dir = tempfile.mkdtemp()
        msi_path = os.path.join(temp_dir, msi_asset['name'])
        print(f"   ⬇️ Downloading {msi_asset['name']}...")
        if not download_file(msi_asset['browser_download_url'], msi_path):
            return False
        
        print("   🛠 Installing (this may require administrator privileges)...")
        subprocess.run(["msiexec", "/i", msi_path, "/quiet", "/norestart"], check=True)
        
        shutil.rmtree(temp_dir, ignore_errors=True)
        
        program_files = os.environ.get("ProgramFiles", "C:\\Program Files")
        gh_path = os.path.join(program_files, "GitHub CLI", "gh.exe")
        if os.path.exists(gh_path):
            add_to_path(os.path.dirname(gh_path))
        
        return True
    except Exception as e:
        print(f"   ❌ MSI installation failed: {str(e)}")
        if temp_dir:
            shutil.rmtree(temp_dir, ignore_errors=True)
        return False


def try_direct_zip_install() -> bool:
    """Fallback ZIP installation for Windows."""
    print("\n   🔄 Attempting direct ZIP installation...")
    temp_dir = ""
    try:
        release_info = get_github_release_info()
        if not release_info:
            return False
        
        zip_asset = next((a for a in release_info.get('assets', []) if a['name'].endswith('windows_amd64.zip')), None)
        if not zip_asset:
            print("   ❌ Could not find Windows ZIP package.")
            return False
            
        temp_dir = tempfile.mkdtemp()
        zip_path = os.path.join(temp_dir, zip_asset['name'])
        print(f"   ⬇️ Downloading {zip_asset['name']}...")
        if not download_file(zip_asset['browser_download_url'], zip_path):
            return False
        
        print("   📦 Extracting...")
        shutil.unpack_archive(zip_path, temp_dir)
        
        bin_dir = next((root for root, _, files in os.walk(temp_dir) if "gh.exe" in files), None)
        if not bin_dir:
            print("   ❌ Could not find gh.exe in extracted files.")
            shutil.rmtree(temp_dir, ignore_errors=True)
            return False
        
        install_dir = os.path.join(os.environ.get("LOCALAPPDATA", ""), "GitHubCLI")
        os.makedirs(install_dir, exist_ok=True)
        
        shutil.copytree(bin_dir, install_dir, dirs_exist_ok=True)
        add_to_path(install_dir)
        
        shutil.rmtree(temp_dir, ignore_errors=True)
        return True
    except Exception as e:
        print(f"   ❌ ZIP installation failed: {str(e)}")
        if temp_dir:
            shutil.rmtree(temp_dir, ignore_errors=True)
        return False


def install_gh_cli_mac() -> bool:
    """macOS installation with multiple methods."""
    if shutil.which("brew"):
        print("\n   🔄 Attempting Homebrew installation...")
        try:
            subprocess.run(["brew", "install", "gh"], check=True, capture_output=True)
            if verify_gh_installation():
                return True
        except subprocess.CalledProcessError as e:
            print(f"   ⚠️ Homebrew failed: {e.stderr.decode(errors='ignore').strip() if e.stderr else 'Unknown error'}")
    
    print("❌ All macOS installation methods failed.")
    return False


def install_gh_cli_linux() -> bool:
    """Linux installation with distro detection and multiple methods."""
    package_managers = [
        ("apt-get", "sudo apt-get update && sudo apt-get install -y gh"),
        ("apt", "sudo apt update && sudo apt install -y gh"),
        ("dnf", "sudo dnf install -y gh"),
        ("yum", "sudo yum install -y gh"),
        ("pacman", "sudo pacman -S --noconfirm github-cli"),
        ("zypper", "sudo zypper install -y gh"),
    ]
    for pm, command in package_managers:
        if shutil.which(pm):
            print(f"\n   🔄 Attempting installation via {pm}...")
            try:
                subprocess.run(command, shell=True, check=True, capture_output=True)
                if verify_gh_installation():
                    return True
            except subprocess.CalledProcessError as e:
                print(f"   ⚠️ {pm} failed: {e.stderr.decode(errors='ignore').strip() if e.stderr else 'Unknown error'}")

    print("❌ All Linux package manager installations failed.")
    return False


def get_github_release_info() -> Optional[dict]:
    """Get latest release info from GitHub API."""
    try:
        with urllib.request.urlopen("https://api.github.com/repos/cli/cli/releases/latest") as response:
            return json.loads(response.read().decode())
    except Exception as e:
        print(f"   ❌ Failed to get release info from GitHub API: {str(e)}")
        return None


def download_file(url: str, path: str) -> bool:
    """Download a file with progress reporting."""
    try:
        def reporthook(count, block_size, total_size):
            if total_size > 0:
                percent = int(count * block_size * 100 / total_size)
                sys.stdout.write(f"\r      Downloading... {percent}%")
                sys.stdout.flush()
            
        urllib.request.urlretrieve(url, path, reporthook=reporthook)
        sys.stdout.write("\r      Downloading... 100%\n")
        sys.stdout.flush()
        return True
    except Exception as e:
        print(f"\n   ❌ Download failed: {str(e)}")
        return False


def add_to_path(directory: str):
    """Add directory to PATH for current session and try making it permanent."""
    print(f"   ✅ Adding {directory} to PATH...")
    os.environ["PATH"] = f"{directory}{os.pathsep}{os.environ['PATH']}"
    
    if platform.system() == "Windows":
        try:
            subprocess.run(
                f'setx PATH "%PATH%;{directory}"',
                shell=True, check=True, capture_output=True
            )
        except Exception as e:
            print(f"   ⚠️ Could not make PATH change permanent: {e}")
            print("      You may need to add it manually.")
    else:
        profile_file = ""
        shell = os.environ.get("SHELL", "")
        if "bash" in shell:
            profile_file = "~/.bashrc"
        elif "zsh" in shell:
            profile_file = "~/.zshrc"
        else:
            profile_file = "~/.profile"
        print(f"   To make this change permanent, add the following to your {profile_file}:")
        print(f'   export PATH="{directory}:$PATH"')


def verify_gh_installation() -> bool:
    """Verify gh is properly installed and in PATH."""
    if not shutil.which("gh"):
        return False
    try:
        result = subprocess.run(["gh", "--version"], check=True, capture_output=True, text=True)
        print(f"✅ GitHub CLI successfully installed: {result.stdout.splitlines()[0]}")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def check_and_install_gh() -> bool:
    """Main function to check and install GitHub CLI with user prompt."""
    if check_gh_installed():
        return True
    
    print("\n❓ GitHub CLI (gh) is required for this feature but is not installed.", file=sys.stderr)
    try:
        answer = input("   Would you like this tool to attempt an automatic installation? (y/n): ").lower().strip()
        if answer != 'y':
            print("\n❌ Installation cancelled by user. Please install gh manually from https://cli.github.com/")
            return False
    except (EOFError, KeyboardInterrupt):
        print("\n❌ Installation cancelled by user.")
        return False
    
    if not install_gh_cli():
        print("\n❌ Failed to install GitHub CLI automatically. Please try manual installation:")
        print("   Visit https://github.com/cli/cli#installation for instructions.")
        return False
    
    if not check_gh_installed():
        print("\n‼️ IMPORTANT: Installation completed, but GitHub CLI is not yet available in this terminal session.")
        print("   Please open a NEW terminal and run your command again.")
        return False
    
    return True


# --- Core Tool Functions ---

def gh_authenticated() -> bool:
    """Check if user is authenticated with github.com using gh."""
    try:
        subprocess.run(
            ["gh", "auth", "status", "-h", "github.com"],
            check=True,
            capture_output=True
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def authenticate_with_gh() -> bool:
    """Authenticate user with GitHub CLI."""
    print("\n🔑 GitHub authentication required.")
    print("The tool will use the GitHub CLI (gh) to open a browser for secure login.")
    print("You may be asked to grant permissions for this tool to create repositories.")
    
    try:
        subprocess.run(
            ["gh", "auth", "login", "--web", "-h", "github.com", "-s", "repo"], 
            check=True
        )
        return True
    except subprocess.CalledProcessError:
        print("❌ Authentication failed. Please try running 'gh auth login -s repo' manually.", file=sys.stderr)
        return False


def initialize_git_repository() -> bool:
    """Initialize git repository if not already initialized."""
    if os.path.exists(".git"):
        return False
        
    print("🛠 Initializing git repository")
    try:
        subprocess.run(["git", "init"], check=True, capture_output=True)
        subprocess.run(["git", "branch", "-M", "main"], check=True, capture_output=True)
        
        if not os.path.exists(".gitignore"):
            with open(".gitignore", "w", encoding="utf-8") as f:
                f.write("""# Python
__pycache__/
*.py[cod]
*.so
.Python
env/
venv/
.env

# IDE
.vscode/
.idea/
*.swp
*.swo

# System
.DS_Store
Thumbs.db

# Project specific
*.log
*.tmp
*.bak
""")
            print("📁 Created .gitignore file")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to initialize Git repository: {e.stderr.decode(errors='ignore').strip()}", file=sys.stderr)
        return False


def create_initial_commit(commit_message: str = "Initial commit") -> bool:
    """Create initial commit if no commits exist."""
    try:
        result = subprocess.run(["git", "rev-list", "--count", "HEAD"], capture_output=True, text=True)
        commit_count = int(result.stdout.strip()) if result.stdout.strip().isdigit() else 0
        
        if commit_count == 0:
            print("📦 Creating initial commit")
            subprocess.run(["git", "add", "."], check=True)
            subprocess.run(["git", "commit", "-m", commit_message], check=True)
            return True
        return False
    except subprocess.CalledProcessError as e:
        error_output = e.stderr.decode(errors='ignore').strip()
        if "nothing to commit" in error_output:
            print(f"❌ Failed to create initial commit: No files found to commit.", file=sys.stderr)
            print("➡️  Add some files to your project directory before creating a repository.", file=sys.stderr)
        else:
            print(f"❌ Failed to create initial commit: {error_output}", file=sys.stderr)
        return False


def create_with_gh_cli(repo_name: str, private: bool = False, description: str = "", commit_message: str = "Initial commit") -> bool:
    """Create and push to new repository using GitHub CLI."""
    try:
        if not os.path.exists(".git"):
            if not initialize_git_repository():
                return False
        
        if not create_initial_commit(commit_message):
            if subprocess.run(["git", "status"], capture_output=True).returncode != 0:
                return False
            print("ℹ️ Using existing commits")

        private_flag = "--private" if private else "--public"
        cmd = ["gh", "repo", "create", repo_name, private_flag, "--source=.", "--remote=origin", "--push"]
        if description:
            cmd.extend(["--description", description])
        
        print("🚀 Creating repository and pushing code...")
        process = subprocess.run(cmd, check=True, capture_output=True, text=True)
        
        repo_url = process.stderr.strip()
        print(f"✅ Successfully created repository: {repo_url}")
        return True
    except subprocess.CalledProcessError as e:
        error_message = e.stderr.strip()
        if "already exists" in error_message:
            print(f"❌ Failed to create repository: {error_message}", file=sys.stderr)
            print("➡️  Please choose a different repository name.", file=sys.stderr)
        else:
            print(f"❌ Failed to create repository: {error_message}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"❌ An unexpected error occurred: {str(e)}", file=sys.stderr)
        return False


def is_local_ahead() -> bool:
    """Check if local branch is ahead of remote tracking branch."""
    try:
        result = subprocess.run(
            ["git", "rev-list", "--left-right", "--count", "origin/main...HEAD"],
            capture_output=True, text=True, check=True
        )
        behind_ahead = result.stdout.strip().split()
        if len(behind_ahead) == 2:
            behind, ahead = map(int, behind_ahead)
            return ahead > 0
        return False
    except subprocess.CalledProcessError:
        return False


def pull_and_check_conflicts(remote: str = "origin", branch: str = "main") -> bool:
    """Pull latest changes from remote and check for merge conflicts."""
    print(f"🔄 Pulling latest changes from {remote}/{branch}...")
    try:
        result = subprocess.run(["git", "pull", remote, branch], capture_output=True, text=True)
        if "CONFLICT" in result.stdout or "CONFLICT" in result.stderr:
            print("❗ Merge conflicts detected.")
            return True
        else:
            print("✅ Pulled successfully. No conflicts.")
            return False
    except subprocess.CalledProcessError as e:
        print(f"❌ Pull failed: {e.stderr or str(e)}", file=sys.stderr)
        return True


def show_merge_conflict_details():
    """Print merge conflict report."""
    print("\n🔍 Merge Conflict Report:\n")
    try:
        result = subprocess.run(["git", "diff", "--name-only", "--diff-filter=U"], capture_output=True, text=True, check=True)
        conflicted_files = result.stdout.strip().splitlines()
        if not conflicted_files:
            print("✅ No merge conflicts found.")
            return

        for file in conflicted_files:
            print(f"📄 File: {file}")
            try:
                with open(file, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()
                    for i, line in enumerate(lines):
                        if line.startswith("<<<<<<<") or line.startswith("=======") or line.startswith(">>>>>>>"):
                            marker = line.strip()
                            print(f"   ⚠️  Conflict Marker ({marker}) at line {i + 1}")
            except Exception as e:
                print(f"   ❌ Could not read file {file}: {str(e)}")
    except subprocess.CalledProcessError as e:
        print(f"❌ Could not retrieve conflicted files: {str(e)}")


def attempt_rebase(remote: str, branch: str) -> bool:
    """Attempt rebase against remote."""
    print(f"🔁 Attempting: git pull --rebase {remote} {branch}")
    try:
        subprocess.run(["git", "pull", "--rebase", remote, branch], check=True)
        print("✅ Rebase completed successfully.")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Rebase failed: {e.stderr.decode(errors='ignore') if e.stderr else str(e)}")
        show_merge_conflict_details()
        return False


def get_git_sync_status(remote: str = "origin", branch: str = "main") -> tuple[str, int, int]:
    """
    Returns a tuple (status, behind, ahead) where status is one of:
    'ahead', 'behind', 'diverged', 'synced', 'unknown'
    """
    try:
        subprocess.run(["git", "fetch", remote], check=True, capture_output=True)
        result = subprocess.run(
            ["git", "rev-list", "--left-right", "--count", f"{remote}/{branch}...{branch}"],
            capture_output=True, text=True, check=True
        )
        behind_str, ahead_str = result.stdout.strip().split()
        behind, ahead = int(behind_str), int(ahead_str)

        if behind > 0 and ahead > 0:
            return "diverged", behind, ahead
        elif ahead > 0:
            return "ahead", behind, ahead
        elif behind > 0:
            return "behind", behind, ahead
        else:
            return "synced", behind, ahead
    except subprocess.CalledProcessError:
        return "unknown", 0, 0


def standard_git_push(commit_message: Optional[str], branch: str, remote: str = "origin", force: bool = False, tags: bool = False) -> bool:
    """Handle standard git push operations."""
    try:
        # Check if there are changes to stage/commit
        diff_info = get_diffstat_summary()
        if diff_info["has_changes"]:
            subprocess.run(["git", "add", "."], check=True)
            if commit_message:
                print(f"📦 Committing with message: '{commit_message}'")
                subprocess.run(["git", "commit", "-m", commit_message, "--allow-empty-message"], check=True)
            else:
                print("ℹ️ Staging uncommitted changes.")
        else:
            if commit_message:
                print(f"📦 Committing with message: '{commit_message}'")
                subprocess.run(["git", "commit", "-m", commit_message, "--allow-empty-message"], check=True)

        # Formulate push command
        push_cmd = ["git", "push"]
        if remote and branch:
            push_cmd.extend([remote, branch])
        
        if force:
            push_cmd.append("--force-with-lease")
            print("⚠️ Using safe force push (--force-with-lease).")
        if tags:
            push_cmd.append("--tags")
        
        print(f"🚀 Executing: {' '.join(push_cmd)}")
        subprocess.run(push_cmd, check=True)
        print("✅ Successfully pushed changes.")
        return True

    except subprocess.CalledProcessError as e:
        error_output = e.stderr.decode(errors='ignore').strip() if e.stderr else str(e)

        if "nothing to commit" in error_output:
            print("ℹ️ No changes to commit. Nothing to do.")
            return True

        if "non-fast-forward" in error_output.lower():
            print("\n❗ Detected non-fast-forward issue. Attempting rebase...")
            if attempt_rebase(remote, branch):
                print("🔁 Retrying push after rebase...")
                return standard_git_push(commit_message, branch, remote, force, tags)
            else:
                print("❌ Rebase failed. Please resolve conflicts manually and re-run the push.")
                return False

        print(f"❌ Push failed: {error_output}", file=sys.stderr)
        return False


# --- Dangerous Command Guard Runner ---

def handle_guard_command(raw_args: List[str], auto_confirm: bool = False) -> int:
    """
    Analyzes an arbitrary dangerous git command, displays lost items/risks,
    and asks for confirmation before executing.
    """
    if not raw_args:
        print(colorize("Usage: gitpush guard <git-command...>", Style.BOLD, Style.YELLOW))
        print("Example: gitpush guard git reset --hard HEAD~5")
        print("         gitpush guard reset --hard HEAD~5")
        return 1

    report = DangerousOperationAnalyzer.analyze_arbitrary_command(raw_args)
    if report and report.is_dangerous:
        # Display the formatted warning box
        print("")
        print(format_danger_box(report))
        
        if not auto_confirm:
            if not prompt_confirm("Continue? [y/N]: "):
                print(colorize("\n🛑 Operation cancelled by user.", Style.BOLD, Style.YELLOW))
                return 1

    # Execute the command
    actual_cmd = ["git"] + ([a for a in raw_args if a.lower() != "git"])
    print(f"\n🚀 Executing: {' '.join(actual_cmd)}")
    try:
        proc = subprocess.run(actual_cmd)
        return proc.returncode
    except Exception as e:
        print(f"❌ Failed to run command: {e}", file=sys.stderr)
        return 1


# --- Main Entry Point ---

def run():
    # Handle status subcommand upfront if detected
    if len(sys.argv) > 1 and sys.argv[1].lower() == "status":
        verbose = "-v" in sys.argv or "--verbose" in sys.argv
        print(format_status_dashboard(verbose=verbose))
        sys.exit(0)

    # Handle guard subcommand upfront if detected
    if len(sys.argv) > 1 and sys.argv[1].lower() in ("guard", "check", "verify-danger"):
        guard_args = sys.argv[2:]
        auto_confirm = ("-y" in guard_args or "--yes" in guard_args)
        clean_args = [a for a in guard_args if a not in ("-y", "--yes")]
        sys.exit(handle_guard_command(clean_args, auto_confirm=auto_confirm))

    parser = argparse.ArgumentParser(
        description="🚀 Supercharged Git push tool with decision-support status dashboard and safety guards",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  Decision status:       gitpush status
  Standard push:         gitpush "My new feature"
  Push without prompt:   gitpush "My new feature" -y
  Dry run preview:       gitpush "My new feature" --dry-run
  Create new repo:       gitpush "Initial commit" --new-repo my-awesome-project
  Private repository:    gitpush "Initial commit" --new-repo my-secret-project --private
  Force push (safe):     gitpush "Rebased feature" --force
  Initialize only:       gitpush --init
  Guard dangerous cmd:   gitpush guard git reset --hard HEAD~5
"""
    )
    parser.add_argument("commit", nargs="?", help="Commit message (optional if just pushing staged/committed changes).")
    parser.add_argument("branch", nargs="?", default=None, help="Branch name (defaults to current branch).")
    parser.add_argument("remote", nargs="?", default="origin", help="Remote name (default: origin).")
    parser.add_argument("--force", action="store_true", help="Force push with --force-with-lease.")
    parser.add_argument("--tags", action="store_true", help="Push all tags.")
    parser.add_argument("--init", action="store_true", help="Initialize a new Git repository and exit.")
    parser.add_argument("--new-repo", metavar="REPO_NAME", help="Create a new GitHub repository with the given name.")
    parser.add_argument("--private", action="store_true", help="Make the new repository private.")
    parser.add_argument("--description", help="Description for the new repository.")
    parser.add_argument("-y", "--yes", action="store_true", help="Skip confirmation prompt and proceed immediately.")
    parser.add_argument("--dry-run", action="store_true", help="Show pre-push preview and inspection without executing.")

    args = parser.parse_args()

    # If --init requested
    if args.init:
        if initialize_git_repository():
            print("✅ Git repository initialized successfully.")
        sys.exit(0)

    # If --new-repo requested
    if args.new_repo:
        if not check_and_install_gh():
            sys.exit(1)
        
        if not gh_authenticated():
            if not authenticate_with_gh():
                sys.exit(1)
        
        if not create_with_gh_cli(
            args.new_repo,
            private=args.private,
            description=args.description or "",
            commit_message=args.commit or "Initial commit"
        ):
            sys.exit(1)
        sys.exit(0)

    # Verify inside git repo
    if not is_git_repo():
        print("❌ Not a Git repository (or any of the parent directories).", file=sys.stderr)
        print("➡️  Run 'gitpush --init' or 'git init' first.", file=sys.stderr)
        sys.exit(1)

    target_branch = args.branch or get_current_branch()
    
    # Run Safety & Pre-Push Inspection
    diff_summary = get_diffstat_summary()
    
    print(format_prepush_summary(
        branch=target_branch,
        remote=args.remote,
        commit_msg=args.commit,
        force=args.force,
        tags=args.tags,
        diff_summary=diff_summary
    ))

    # If dry-run requested, exit here
    if args.dry_run:
        print(colorize("🔍 Dry-run complete. No changes were made.", Style.BOLD, Style.CYAN))
        sys.exit(0)

    # Confirmation Prompt (unless -y / --yes is passed)
    if not args.yes:
        if not prompt_confirm("Continue? [y/N]: "):
            print(colorize("\n🛑 Push cancelled by user.", Style.BOLD, Style.YELLOW))
            sys.exit(0)

    # Remote sync checking
    sync_status, behind, ahead = get_git_sync_status(args.remote, target_branch)
    if sync_status != "unknown":
        print(f"\n📊 Git status: {sync_status.upper()} (Behind: {behind}, Ahead: {ahead})")

    if sync_status == "behind" and not args.force:
        print("🔄 Your branch is behind remote. Pulling latest changes...")
        if pull_and_check_conflicts(args.remote, target_branch):
            show_merge_conflict_details()
            print("\n❌ Resolve conflicts before pushing.")
            sys.exit(1)

    elif sync_status == "diverged" and not args.force:
        print("⚠️ Your branch has diverged from remote. Rebase recommended.")
        if attempt_rebase(args.remote, target_branch):
            print("✅ Rebase done. Proceeding to push...")
        else:
            print("❌ Rebase failed. Please resolve manually.")
            sys.exit(1)

    if not standard_git_push(
        args.commit,
        target_branch,
        args.remote,
        args.force,
        args.tags
    ):
        sys.exit(1)


if __name__ == "__main__":
    run()