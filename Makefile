PY ?= python
.PHONY: install migrate run-api run-worker run-web run-prod test lint check
install:
	$(PY) -m pip install -r requirements-dev.txt && cd web && npm install
migrate:
	alembic upgrade head
run-api:
	uvicorn app.main:app --reload --port 8000
run-worker:
	$(PY) -m pipeline worker
run-web:
	cd web && npm run dev
# One environment: production. Built web bundle + API without reload, using the real .env / DATABASE_URL.
run-prod:
	cd web && npm run build && npm run preview &
	QUEUE_MODE=thread uvicorn app.main:app --port 8000
test:
	pytest -q
lint:
	ruff check . && mypy app

# One command that runs every check (replaces the repeated lint/types/tests/build calls)
check:
	ruff check . && mypy app && pytest -q -p no:warnings && cd web && npm run build
