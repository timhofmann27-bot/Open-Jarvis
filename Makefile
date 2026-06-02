# Open-Jarvis Makefile
# Convenience targets for common development tasks

.PHONY: help install dev-install test lint format type-check clean pre-commit all

PYTHON ?= python
PIP    ?= pip

help:  ## Show this help message
	@echo "Open-Jarvis — common commands:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install:  ## Install runtime dependencies
	$(PIP) install -r requirements.txt

dev-install:  ## Install development dependencies (includes runtime)
	$(PIP) install -r requirements-dev.txt
	pre-commit install

test:  ## Run self-test suite
	$(PYTHON) -c "import sys; sys.path.insert(0, '.'); from core.test_suite import TestSuite; t = TestSuite(); t.run_all()"

test-verbose:  ## Run self-test suite with verbose output
	$(PYTHON) -c "import sys; sys.path.insert(0, '.'); from core.test_suite import TestSuite; t = TestSuite(); t.run_all(verbose=True)"

self-improve:  ## Run self-improvement cycle
	$(PYTHON) -c "import sys; sys.path.insert(0, '.'); from core.self_improver import SelfImprover; print(SelfImprover().get_report())"

health:  ## Run self-healing health check
	$(PYTHON) -c "import sys; sys.path.insert(0, '.'); from core.self_healer import SelfHealer; h = SelfHealer(); h.check_all(); print(h.get_health_summary())"

lint:  ## Run ruff linter
	ruff check .

lint-fix:  ## Run ruff linter with auto-fix
	ruff check --fix .

format:  ## Format code with ruff + black
	ruff format .
	black .

format-check:  ## Check formatting without changes
	ruff format --check .
	black --check .

type-check:  ## Run mypy
	mypy core actions

pre-commit:  ## Run all pre-commit hooks on all files
	pre-commit run --all-files

pre-commit-update:  ## Update pre-commit hooks to latest versions
	pre-commit autoupdate

ci: lint format-check type-check test  ## Run all CI checks locally

clean:  ## Remove build artifacts
	rm -rf build/ dist/ *.egg-info .pytest_cache .ruff_cache .mypy_cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete
	find . -name "*.bak" -delete

clean-all: clean  ## Deep clean (including memory, desktop, etc.)
	@echo "This will DELETE memory/, desktop/, listener.log"
	@echo "Press Ctrl-C to abort, or wait 5s to continue..."
	@sleep 5
	rm -rf memory/ desktop/ listener.log

run:  ## Run JARVIS
	$(PYTHON) main.py

run-local:  ## Run JARVIS in local LLM mode
	$(PYTHON) -c "import sys; sys.path.insert(0, '.'); from main import JarvisLive; from ui import JarvisUI; ui = JarvisUI('face.png'); jarvis = JarvisLive(ui); jarvis._use_local_llm = True; import asyncio; asyncio.run(jarvis.run())"

run-tests-ci:  ## Run tests in CI mode (strict, no network)
	$(PYTHON) -c "import sys; sys.path.insert(0, '.'); from core.test_suite import TestSuite; t = TestSuite(); r = t.run_all(); sys.exit(0 if r['failed'] == 0 else 1)"

docs-serve:  ## Serve documentation locally
	@echo "Install mkdocs-material first: pip install mkdocs-material"
	mkdocs serve

deps-update:  ## Update all dependencies
	$(PIP) install --upgrade -r requirements.txt
	$(PIP) install --upgrade -r requirements-dev.txt
