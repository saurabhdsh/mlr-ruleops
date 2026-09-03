FROM python:3.12-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app:/worker

COPY backend/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY backend/ /app
COPY worker/ /worker

WORKDIR /worker
CMD ["celery", "-A", "celery_app:celery", "worker", "--loglevel=info"]
