FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

# Render (and most PaaS) inject $PORT -- fall back to 8000 for local/docker-compose use.
CMD ["sh", "-c", "export BACKEND_HOST=$(echo $BACKEND_URL | sed -E 's#https?://##; s#/.*##') && envsubst '${PORT} ${BACKEND_URL} ${BACKEND_HOST}' < /etc/nginx/templates/default.conf.template > /etc/nginx/conf.d/default.conf && nginx -g 'daemon off;'"]
