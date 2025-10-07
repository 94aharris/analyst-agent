.PHONY: run
run:
	uv run fastapi run src/main.py

.PHONY: dev
dev:
	uv run fastapi dev src/main.py

.PHONY: lint
lint:
	uv run ruff check .

.PHONY: lint-fix
lint-fix:
	uv run ruff check --fix .
