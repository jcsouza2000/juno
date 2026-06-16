FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

COPY janus/backend/requirements.txt /app/requirements.txt

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY juno_audit /app/juno_audit
RUN pip install --no-cache-dir /app/juno_audit

COPY janus/backend/app /app/app
COPY janus/backend/alembic /app/alembic
COPY janus/backend/alembic.ini /app/alembic.ini
COPY janus/backend/entrypoint.sh /app/entrypoint.sh
RUN sed -i 's/\r$//' /app/entrypoint.sh && chmod +x /app/entrypoint.sh

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/health/ready').read()" || exit 1

CMD ["sh", "/app/entrypoint.sh"]
