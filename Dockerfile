# QuantDinger All-in-One Dockerfile — Easypanel ready
# Build: docker build -t quantdinger:latest .
# Run:  docker run -p 8080:80 quantdinger:latest
#
# Required env vars (set in Easypanel):
#   DATABASE_URL      — PostgreSQL connection string
#   REDIS_HOST        — Redis host
#   SECRET_KEY        — Flask secret key (auto-generated if missing)

# ── Build: Python deps ──────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

COPY backend_api_python/requirements.txt ./requirements.txt

RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Build: frontend (prebuilt, just copy) ────────────────────────────────────
FROM nginx:1.25-alpine AS frontend
COPY frontend/nginx.conf /tmp/default.conf
COPY frontend/dist/ /usr/share/nginx/html/

# ── Runtime ───────────────────────────────────────────────────────────────────────
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 postgresql-client curl tini supervisor nginx \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Python deps from builder
COPY --from=builder /install /usr/local

# App code
COPY backend_api_python/ .

# Frontend static files
COPY --from=frontend /usr/share/nginx/html/ /usr/share/nginx/html/
# Nginx config: replace the default Debian site
COPY --from=frontend /tmp/default.conf /etc/nginx/sites-enabled/default

# Entrypoint + supervisord config
COPY supervisord.conf /etc/supervisord.conf
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Make venv pip available alongside system pip
ENV PATH="/usr/local/bin:$PATH"

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost/health || exit 1

ENTRYPOINT ["/entrypoint.sh"]
CMD ["/usr/bin/tini", "--", "supervisord", "-c", "/etc/supervisord.conf"]
