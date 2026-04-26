#!/bin/bash
set -e

# ── Render config templates with environment variables ──────
# Loki, Tempo, and Prometheus configs use ${VAR} placeholders
# that need to be replaced with actual env var values at runtime.

# ── Set defaults for optional env vars ──────────────────────
export LOKI_AZURE_CONTAINER="${LOKI_AZURE_CONTAINER:-SphereVoice-loki-chunks}"
export TEMPO_AZURE_CONTAINER="${TEMPO_AZURE_CONTAINER:-SphereVoice-tempo-traces}"
export BACKEND_METRICS_TARGET="${BACKEND_METRICS_TARGET:-SphereVoice-backend:80}"

echo "[entrypoint] Rendering config templates..."
echo "[entrypoint]   Storage account: $AZURE_STORAGE_ACCOUNT"
echo "[entrypoint]   Loki container:  $LOKI_AZURE_CONTAINER"
echo "[entrypoint]   Tempo container: $TEMPO_AZURE_CONTAINER"
echo "[entrypoint]   Backend target:  $BACKEND_METRICS_TARGET"

# Loki config
envsubst < /etc/loki/loki.yml.tmpl > /etc/loki/loki.yml

# Tempo config
envsubst < /etc/tempo/tempo.yml.tmpl > /etc/tempo/tempo.yml

# Prometheus config
envsubst < /etc/prometheus/prometheus.yml.tmpl > /etc/prometheus/prometheus.yml

echo "[entrypoint] Configs rendered."

# ── Ensure data directories have correct ownership ──────────
chown -R grafana:grafana /data/grafana 2>/dev/null || true

# ── Start supervisord ───────────────────────────────────────
exec /usr/bin/supervisord -c /etc/supervisor/conf.d/observability.conf
