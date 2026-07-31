.PHONY: sync format format-check lint typecheck test check workflow-lint build package-smoke clean

# Default Python version for local dev
PYTHON ?= python3

# uv command
UV ?= uv

# Activate the virtual environment for targets that need it
SYNC_TARGET = $(UV) sync --frozen --extra dev

sync: ## Sync dependencies from uv.lock
	$(SYNC_TARGET)

format: ## Auto-format code with ruff
	$(UV) run ruff format src tests
	$(UV) run ruff check --fix src tests

format-check: ## Check formatting without modifying
	$(UV) run ruff format --check src tests
	$(UV) run ruff check src tests

lint: ## Run ruff linter
	$(UV) run ruff check src tests

typecheck: ## Run mypy strict
	$(UV) run mypy --strict src

test: ## Run pytest with coverage
	$(UV) run pytest

check: format-check lint typecheck test ## Run all quality gates

workflow-lint: ## Lint GitHub workflow files (actionlint + zizmor)
	@if command -v actionlint >/dev/null 2>&1; then \
		actionlint; \
	else \
		echo "WARNING: actionlint not installed, skipping"; \
	fi
	@if command -v zizmor >/dev/null 2>&1; then \
		zizmor .github/workflows/; \
	else \
		echo "WARNING: zizmor not installed, skipping"; \
	fi
	@bash scripts/verify_workflows.sh

build: ## Build wheel and sdist
	$(UV) build

package-smoke: build ## Build and smoke-test in a clean virtual environment
	$(UV) run python scripts/package_smoke.py

clean: ## Remove build artifacts and caches
	rm -rf dist build *.egg-info src/*.egg-info
	rm -rf .mypy_cache .ruff_cache .pytest_cache
	rm -rf htmlcov .coverage coverage.xml
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
