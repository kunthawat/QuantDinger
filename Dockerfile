# QuantDinger All-in-One Dockerfile for Easypanel Deployment
# Serves prebuilt Vue frontend via nginx + proxies API to Flask/gunicorn backend
# PostgreSQL and Redis are expected as external Easypanel addons

ARG BASE_IMAGE=python:3.12-slim-bookworm

# ─── Backend stage ───────────────────────────────────────────────────────────
FROM ${BASE_IMAGE} AS backend-builder

WORKDIR /app

# Apt: Aliyun mirror first, then official Debian fallback
RUN set -eux; \
    APT_TIMEOUT='Acquire::http::Timeout=35'; \
    if [ -f /etc/apt/sources.list.d/debian.sources ]; then \
      cp /etc/apt/sources.list.d/debian.sources /tmp/debian.sources.bak; \
      sed -i -E \
        's|https?://deb.debian.org|https://mirrors.aliyun.com|g; s|https?://security.debian.org|https://mirrors.aliyun.com|g' \
        /etc/apt/sources.list.d/debian.sources; \
      if ! apt-get -o "$APT_TIMEOUT" -o Acquire::https::Timeout=35 update; then \
        cp /tmp/debian.sources.bak /etc/apt/sources.list.d/debian.sources; \
        sed -i 's|http://deb.debian.org|https://deb.debian.org|g' /etc/apt/sources.list.d/*.sources 2>/dev/null || true; \
        apt-get -o "$APT_TIMEOUT" update; \
      fi; \
    else \
      sed -i 's|http://deb.debian.org|https://deb.debian.org|g' /etc/apt/sources.list.d/*.sources 2>/dev/null || true; \
      apt-get -o "$APT_TIMEOUT" update; \
    fi; \
    apt-get install -y --no-install-recommends --fix-missing \
      ca-certificates curl build-essential python3-dev libffi-dev libssl-dev \
    && rm -rf /var/lib/apt/lists/*

COPY backend_api_python/requirements.txt .

# Pip: Aliyun PyPI first, then PyPI.org fallback
RUN set -eux; \
    python3 -m venv /app/venv; \
    /app/venv/bin/pip install --no-cache-dir --prefer-binary --timeout 180 \
        -i https://mirrors.aliyun.com/pypi/simple/ \
        -r requirements.txt \
      || /app/venv/bin/pip install --no-cache-dir --prefer-binary --timeout 180 -r requirements.txt; \
    apt-get purge -y --auto-remove build-essential python3-dev libffi-dev libssl-dev; \
    rm -rf /var/lib/apt/lists/*

COPY backend_api_python/ .

RUN mkdir -p logs data/memory

# ─── Frontend stage ───────────────────────────────────────────────────────────
FROM nginx:1.25-alpine AS frontend

RUN printf '%s\n' \
    'server {' \
    '    listen 80;' \
    '    server_name localhost;' \
    '    root /usr/share/nginx/html;' \
    '    index index.html;' \
    '' \
    '    gzip on;' \
    '    gzip_vary on;' \
    '    gzip_min_length 1000;' \
    '    gzip_comp_level 6;' \
    '    gzip_types text/plain text/css application/json application/javascript text/xml application/xml application/xml+rss text/javascript image/svg+xml;' \
    '' \
    '    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot|map)$ {' \
    '        expires 1y;' \
    '        add_header Cache-Control "public, immutable";' \
    '        access_log off;' \
    '    }' \
    '' \
    '    # API proxy to gunicorn on localhost (co-located in same container)' \
    '    location /api/ {' \
    '        proxy_pass http://127.0.0.1:5000/api/;' \
    '        proxy_http_version 1.1;' \
    '        proxy_set_header Upgrade $http_upgrade;' \
    '        proxy_set_header Connection '"'"'upgrade'"'"';' \
    '        proxy_set_header Host $host;' \
    '        proxy_set_header X-Real-IP $remote_addr;' \
    '        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;' \
    '        proxy_set_header X-Forwarded-Proto $scheme;' \
    '        proxy_cache_bypass $http_upgrade;' \
    '        proxy_read_timeout 600s;' \
    '        proxy_connect_timeout 75s;' \
    '        proxy_send_timeout 600s;' \
    '        client_max_body_size 10m;' \
    '    }' \
    '' \
    '    location / {' \
    '        try_files $uri $uri/ /index.html;' \
    '    }' \
    '' \
    '    location /health {' \
    '        return 200 '"'"'OK'"'"';' \
    '        add_header Content-Type text/plain;' \
    '        access_log off;' \
    '    }' \
    '}' \
    > /etc/nginx/conf.d/default.conf

COPY frontend/dist/ /usr/share/nginx/html/

# ─── Final stage ─────────────────────────────────────────────────────────────
FROM ${BASE_IMAGE} AS final

WORKDIR /app

# Install nginx, runtime deps, and curl (for healthcheck)
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
      ca-certificates curl nginx supervisor \
    && rm -rf /var/lib/apt/lists/*

# Copy backend from builder
COPY --from=backend-builder /app /app

# Copy nginx + supervisord config
COPY --from=frontend /etc/nginx/conf.d /etc/nginx/conf.d
COPY --from=frontend /usr/share/nginx/html /usr/share/nginx/html

# Entrypoint handles SECRET_KEY auto-generation (same logic as original)
COPY backend_api_python/docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN sed -i 's/\r$//' /usr/local/bin/docker-entrypoint.sh \
    && chmod +x /usr/local/bin/docker-entrypoint.sh

# Supervisord config: runs both nginx and gunicorn (venv gunicorn in PATH)
# Nginx proxies /api/ to gunicorn on localhost since they're co-located
RUN printf '%s\n' \
    '[supervisord]' \
    'nodaemon=true' \
    'logfile=/var/log/supervisor/supervisord.log' \
    'pidfile=/var/run/supervisord.pid' \
    '' \
    '[program:nginx]' \
    'command=nginx -g "daemon off;"' \
    'stdout_logfile=/dev/stdout' \
    'stderr_logfile=/dev/stderr' \
    'autorestart=true' \
    '' \
    '[program:gunicorn]' \
    'command=/app/venv/bin/gunicorn -c /app/gunicorn_config.py run:app' \
    'directory=/app' \
    'stdout_logfile=/dev/stdout' \
    'stderr_logfile=/dev/stderr' \
    'autorestart=true' \
    'stopasgroup=true' \
    > /etc/supervisor/conf.d/supervisord.conf

EXPOSE 80

ENV PYTHONUNBUFFERED=1
ENV PYTHON_API_HOST=0.0.0.0
ENV PYTHON_API_PORT=5000

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD ["supervisord"]
