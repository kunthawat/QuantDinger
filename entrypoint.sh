#!/bin/bash
set -e

echo "============================================"
echo "  QuantDinger — Starting..."
echo "============================================"

# Auto-generate SECRET_KEY if missing or default
if [ ! -f /app/.env ]; then
    if [ -f /app/env.example ]; then
        cp /app/env.example /app/.env
        echo "[INFO] Created .env from env.example"
    fi
fi

if [ -f /app/.env ]; then
    DEFAULT_SECRET="quantdinger-secret-key-change-me"
    CURRENT_SECRET=$(grep -E "^SECRET_KEY=" /app/.env 2>/dev/null | cut -d'=' -f2- | tr -d '"' | tr -d "'" | xargs || echo "")

    if [ -z "$CURRENT_SECRET" ]; then
        NEW_SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")
        echo "SECRET_KEY=${NEW_SECRET}" >> /app/.env
        echo "[AUTO] Generated random SECRET_KEY (was missing)"
    elif [ "$CURRENT_SECRET" = "$DEFAULT_SECRET" ]; then
        NEW_SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")
        sed -i "s|SECRET_KEY=.*|SECRET_KEY=${NEW_SECRET}|" /app/.env
        echo "[AUTO] Generated random SECRET_KEY (was default)"
    fi
fi

echo "[OK]  SECRET_KEY configured"

# Create dirs
mkdir -p /app/logs /app/data/memory

# Ownership
chown -R nobody:nogroup /app/logs /app/data 2>/dev/null || true

echo ""
exec "$@"
