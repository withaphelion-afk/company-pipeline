PY ?= python
.PHONY: install migrate run-api run-worker run-web test lint
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
test:
	pytest -q
lint:
	ruff check . && mypy app
