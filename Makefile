.PHONY: install migrate backend frontend test lint

install:
	cd backend && uv sync
	cd frontend && npx -y npm@11 install

migrate:
	cd backend && uv run alembic upgrade head

backend:
	cd backend && uv run fastapi dev app/main.py --port 8000

frontend:
	cd frontend && npm run dev

test:
	cd backend && uv run pytest -q

lint:
	cd backend && uv run ruff check . && uv run ruff format --check .
	cd frontend && npm run lint
