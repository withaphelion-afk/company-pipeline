FROM python:3.12-slim
WORKDIR /app
ENV PYTHONPATH=/app PYTHONUNBUFFERED=1 QUEUE_MODE=thread LLM_PROVIDER=template DATA_DIR=/tmp/data
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY alembic.ini .
COPY app app
COPY migrations migrations
COPY pipeline pipeline
COPY templates templates
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
