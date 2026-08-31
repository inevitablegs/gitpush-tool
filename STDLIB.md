# GitPush Tool — Standard Library Substitution Log (STDLIB.md)

This document serves as the official **Standard Library Substitution Log** for **GitPush Tool**, submitted to the **Zero Dependency 2026 — 72-Hour Hackathon** (Track A: Developer Tools & CLI) organized by **Hackathon Raptors**.

---

## 📌 The Zero-Dependency Challenge

The challenge requires an empty runtime dependency manifest (`install_requires=[]`) with zero third-party packages from PyPI.

This log documents **10 meaningful standard-library-for-package substitutions** implemented in GitPush, explaining why developers normally reach for external packages and how Python's built-in modules replace them.

---

## 📊 Summary Table of Substitutions

| # | Normally Used Package | Why Developers Reach For It | Standard Library Replacement | GitPush Implementation Code Paths |
|---|---|---|---|---|
| 1 | **GitPython** / **pygit2** / **dulwich** | High-level Python API for interacting with Git repositories | `subprocess` calling native Git plumbing | `gitpush/safety.py`, `gitpush/status.py`, `gitpush/sync.py`, `gitpush/undo.py` (`run_git()`, `subprocess.run()`) |
| 2 | **click** / **typer** / **fire** | Command-line option parsing and subcommand routing | `argparse` & `sys.argv` dispatch | `gitpush/cli.py` (`argparse.ArgumentParser`, `sys.argv` subcommand routing) |
| 3 | **rich** / **colorama** / **termcolor** | ANSI color styling, formatting, and terminal UI boxes | Standard ANSI escape codes & TTY detection | `gitpush/safety.py` (`Style` class, `supports_color()`, `colorize()`) |
| 4 | **requests** / **httpx** / **urllib3** | Making HTTP GET requests to fetch remote release assets | `urllib.request` | `gitpush/cli.py` (`urllib.request.urlopen()`, `urllib.request.urlretrieve()`) |
| 5 | **ujson** / **orjson** | JSON payload parsing and serialization | `json` | `gitpush/cli.py` (`json.loads()`) |
| 6 | **pathlib2** / **boltons.fileutils** | Filesystem path management and directory traversing | `pathlib.Path` & `os.path` | `setup.py`, `gitpush/safety.py`, `gitpush/cli.py` (`Path(__file__)`, `os.path.join()`) |
| 7 | **pytest** / **tox** / **nose2** | Automated unit test discovery, assertions, and test runners | `unittest` | `tests/test_status.py`, `tests/test_sync.py`, `tests/test_undo.py` (`unittest.TestCase`) |
| 8 | **pytest-tmpdir** / **py.path** | Isolated temporary directory fixtures for file-based tests | `tempfile` & `shutil` | `tests/test_status.py`, `tests/test_sync.py`, `tests/test_undo.py` (`tempfile.mkdtemp()`, `shutil.rmtree()`) |
| 9 | **shutilwhich** / **whichcraft** | Cross-platform binary lookup on system PATH | `shutil.which` | `gitpush/cli.py` (`shutil.which("gh")`, `shutil.which("winget")`) |
| 10 | **distro** / **platformdirs** | Operating system detection and machine architecture inspection | `platform` & `os.environ` | `gitpush/cli.py` (`platform.system()`, `platform.machine()`, `os.environ`) |

---

## 🔍 Detailed Substitution Breakdowns

### 1. Git Repository Interaction
- **Normally Used:** `GitPython`, `pygit2`, `dulwich`
- **Why Developers Use It:** Avoids writing command execution boilerplate and provides high-level objects like `Repo`, `Commit`, `Tree`, and `Index`.
- **Standard Library Approach:** `subprocess.run()` executing native Git plumbing and porcelain commands (`git rev-parse`, `git status --porcelain=v1`, `git diff --numstat`, `git rev-list`, `git merge-base`).
- **Why It's Better in GitPush:** Direct invocation of native Git is significantly faster, avoids memory leaks common in large Python Git object models, eliminates dozens of megabytes of C extension bindings (`libgit2`), and guarantees compatibility with the user's installed Git version.

### 2. CLI Argument Parsing & Routing
- **Normally Used:** `click`, `typer`
- **Why Developers Use It:** Decorator-based syntax for command trees, automatic help formatting, and type casting.
- **Standard Library Approach:** `argparse.ArgumentParser` combined with clean `sys.argv` dispatching for top-level subcommands (`status`, `undo`, `guard`, `sync`).
- **Why It's Better in GitPush:** Starts up instantly with zero import overhead and no external dependency tree.

### 3. Terminal Styling & Color Highlights
- **Normally Used:** `rich`, `colorama`, `termcolor`
- **Why Developers Use It:** ANSI formatting strings, table rendering, and cross-platform Windows console handling.
- **Standard Library Approach:** A lightweight `Style` class with standard ANSI escape codes (`\033[92m`, `\033[91m`, etc.), combined with `sys.stdout.isatty()` and `NO_COLOR` environment variable checks.
- **Why It's Better in GitPush:** Implements full dashboard, box formatting, diff highlighting, and health bars in fewer than 40 lines of clean Python.

### 4. HTTP Requests & Downloads
- **Normally Used:** `requests`, `httpx`
- **Why Developers Use It:** Simple API for GET requests, JSON response decoding, and file streaming.
- **Standard Library Approach:** `urllib.request.urlopen()` and `urllib.request.urlretrieve()` with a custom `reporthook` callback to display progress percentages in stdout.
- **Why It's Better in GitPush:** Accomplishes GitHub API release checks and binary downloads without importing external networking stacks or SSL bundles (`certifi`, `urllib3`, `idna`).

### 5. JSON Deserialization
- **Normally Used:** `ujson`, `orjson`
- **Why Developers Use It:** Fast C-accelerated JSON encoding/decoding.
- **Standard Library Approach:** `json.loads()` and `json.dumps()`.
- **Why It's Better in GitPush:** GitHub API responses in GitPush are small payloads (<50KB), making standard library `json` instantaneous without needing C-compiled wheels.

### 6. Filesystem & Path Utilities
- **Normally Used:** `pathlib2`, `boltons.fileutils`
- **Why Developers Use It:** Backported object-oriented path handling and recursive directory helpers.
- **Standard Library Approach:** Built-in `pathlib.Path`, `os.path.join()`, `os.path.basename()`, and `os.walk()`.
- **Why It's Better in GitPush:** Fully native across modern Python 3.6+ across Windows, macOS, and Linux.

### 7. Unit Testing Framework
- **Normally Used:** `pytest`
- **Why Developers Use It:** Plain `assert` statements, test discovery, and fixture injection.
- **Standard Library Approach:** Built-in `unittest.TestCase` with `setUp()`, `tearDown()`, and `unittest.main()`.
- **Why It's Better in GitPush:** Enables developers and CI runners to execute the complete test suite out-of-the-box (`python -m unittest discover tests/`) without installing a single testing dependency.

### 8. Temporary Directory Fixtures
- **Normally Used:** `pytest-tmpdir`, `py.path`
- **Why Developers Use It:** Automated creation and garbage collection of temporary filesystem paths.
- **Standard Library Approach:** `tempfile.mkdtemp()` in test `setUp()` and `shutil.rmtree(..., ignore_errors=True)` in `tearDown()`.
- **Why It's Better in GitPush:** Provides complete filesystem isolation for creating bare Git remotes and temporary clones during test runs.

### 9. Executable Lookup
- **Normally Used:** `shutilwhich`, `whichcraft`
- **Why Developers Use It:** Resolving executable binaries across platform PATH variables.
- **Standard Library Approach:** `shutil.which()`.
- **Why It's Better in GitPush:** Built directly into Python's `shutil` module since Python 3.3.

### 10. Platform & OS Introspection
- **Normally Used:** `distro`, `platformdirs`
- **Why Developers Use It:** Identifying Linux distribution families and OS architecture.
- **Standard Library Approach:** `platform.system()`, `platform.machine()`, and `os.environ`.
- **Why It's Better in GitPush:** Accurately differentiates Windows, macOS, and Linux package manager commands (`winget`, `brew`, `apt-get`, `pacman`, etc.) with zero dependencies.

---

## 🔍 Independent Verification

To verify that GitPush contains zero runtime dependencies:

```bash
# Check manifest requirements in setup.py
python -c "import setup; print('Dependencies:', setup.setup_kwargs.get('install_requires', []))"

# Run full test suite using standard library unittest
python -m unittest discover tests/
```
