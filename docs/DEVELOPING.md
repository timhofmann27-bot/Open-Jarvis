# Development Guide

A quick reference for working on Open-Jarvis.

## Quick Commands

```bash
make help           # Show all available commands
make install        # Install runtime deps
make dev-install    # Install dev deps + pre-commit
make test           # Run self-test suite
make lint           # Lint with ruff
make format         # Auto-format code
make type-check     # mypy on core/ and actions/
make pre-commit     # Run all pre-commit hooks
make ci             # Run all CI checks locally
make clean          # Remove build artifacts
make run            # Run JARVIS
```

See [Makefile](../Makefile) for the full list.

## Pre-Commit Workflow

```bash
# One-time setup
pip install -r requirements-dev.txt
pre-commit install

# Before every commit (automatic)
git add .
git commit -m "..."  # hooks run automatically

# Manual run on all files
pre-commit run --all-files

# Update hook versions
pre-commit autoupdate
```

## Linting

The project uses [Ruff](https://docs.astral.sh/ruff/) for linting + formatting (configured in `pyproject.toml`):

```bash
ruff check .              # Lint
ruff check --fix .        # Lint with auto-fix
ruff format .             # Format
ruff format --check .     # Format check (CI)
```

### Ignored Rules

Some rules are intentionally disabled (see `pyproject.toml [tool.ruff.lint].ignore`):
- `E501` — line too long (handled by formatter)
- `E402` — import not at top (we use lazy imports for fast startup)
- `E722` — bare except (we allow this for safety)
- `N806` — uppercase variable (we use `UPPER_SNAKE` for constants)

## Type Checking

[mypy](https://mypy.readthedocs.io/) runs in non-strict mode (see `pyproject.toml [tool.mypy]`):

```bash
mypy core actions
```

`mypy.ini` is not used — config is in `pyproject.toml`. Stubs for third-party libraries are not required (`ignore_missing_imports = true`).

## Testing

Self-test suite is in `core/test_suite.py`. 94 tests across 6 suites:

| Suite | What it tests |
|-------|---------------|
| imports | All modules can be imported without errors |
| configs | All config JSON files are valid |
| core | Core systems (memory, self-*, etc.) |
| actions | All action modules have function definitions |
| network | DNS resolution, HTTP connectivity, API keys |
| api | Local HTTP server endpoints respond |

Run with:
```bash
make test
```

Or via dashboard: http://localhost:8080/ → Tests tab.

## Adding a New Module

1. Create the file (e.g., `actions/my_tool.py` or `core/my_system.py`)
2. Add tests in `core/test_suite.py`
3. Wire it up in `main.py` if needed
4. Add documentation
5. Run `make ci` before committing

## Release Process

1. Update `CHANGELOG.md` with version + date
2. Update version in `pyproject.toml`
3. Tag the release: `git tag -a v1.0.0 -m "Release 1.0.0"`
4. Push tag: `git push --tags`
5. Create GitHub release with changelog excerpt

## Project Conventions

- **Async code**: Use `asyncio` and `async/await` consistently
- **Lazy imports**: Import heavy modules inside functions (e.g., `playwright`, `docker`) to keep startup fast
- **Error handling**: Catch specific exceptions, log with `[MODULE]` prefix
- **Logging**: Use `print()` for user-facing output, `logging` for internal
- **UI state**: `LISTENING` → `THINKING` → `SPEAKING` → `LISTENING`
- **Config files**: Always commit `.example` versions with empty values
