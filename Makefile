# Backend commands
.PHONY: run
run:
	uv run fastapi run src/main.py

.PHONY: dev
dev:
	uv run fastapi dev src/main.py

.PHONY: install
install:
	uv sync

# Frontend commands
.PHONY: frontend-install
frontend-install:
	cd frontend && npm install

.PHONY: frontend-dev
frontend-dev:
	cd frontend && npm run dev

.PHONY: frontend-build
frontend-build:
	cd frontend && npm run build

# Run both backend and frontend in dev mode
.PHONY: dev-all
dev-all:
	@echo "Starting backend and frontend in parallel..."
	@trap 'kill 0' INT; \
	uv run fastapi dev src/main.py & \
	cd frontend && npm run dev & \
	wait

# Linting and formatting
.PHONY: lint
lint:
	uv run ruff check .

.PHONY: lint-fix
lint-fix:
	uv run ruff check --fix .

.PHONY: format
format:
	uv run ruff format .

# Database commands
.PHONY: db-clean
db-clean:
	rm -f chatkit.sqlite
	@echo "Database cleaned"

# Development setup
.PHONY: setup
setup: install frontend-install
	@echo "Setup complete! Run 'make dev-all' to start development"

# Clean build artifacts and caches
.PHONY: clean
clean:
	rm -rf .venv
	rm -rf .ruff_cache
	rm -rf frontend/node_modules
	rm -rf frontend/dist
	rm -f chatkit.sqlite
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	@echo "Cleaned all build artifacts and caches"

# Help command
.PHONY: help
help:
	@echo "Available commands:"
	@echo "  make install          - Install Python dependencies with uv"
	@echo "  make dev              - Run FastAPI backend in dev mode"
	@echo "  make run              - Run FastAPI backend in production mode"
	@echo "  make frontend-install - Install frontend dependencies"
	@echo "  make frontend-dev     - Run frontend dev server"
	@echo "  make frontend-build   - Build frontend for production"
	@echo "  make dev-all          - Run both backend and frontend in dev mode"
	@echo "  make setup            - Initial setup (install all dependencies)"
	@echo "  make lint             - Run ruff linter"
	@echo "  make lint-fix         - Run ruff linter with auto-fix"
	@echo "  make format           - Format code with ruff"
	@echo "  make db-clean         - Delete SQLite database"
	@echo "  make clean            - Remove all build artifacts and caches"
	@echo "  make help             - Show this help message"
