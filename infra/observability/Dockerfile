# SphereVoice Observability Stack — All-in-One Production Image
# Runs Grafana + Loki + Tempo + Prometheus + OTEL Collector via supervisord
# Designed for Azure Container Apps deployment (single container, persistent volume)

FROM ubuntu:22.04

ARG GRAFANA_VERSION=11.2.0
ARG LOKI_VERSION=3.2.0
ARG TEMPO_VERSION=2.5.0
ARG PROMETHEUS_VERSION=2.54.1
ARG OTEL_VERSION=0.108.0

ENV DEBIAN_FRONTEND=noninteractive

# ── Install supervisor + nginx + dependencies ──────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    supervisor nginx wget ca-certificates adduser libfontconfig1 musl curl unzip gettext-base \
    && rm -rf /var/lib/apt/lists/*

# ── Download Grafana ────────────────────────────────────────
RUN wget -q "https://dl.grafana.com/oss/release/grafana_${GRAFANA_VERSION}_amd64.deb" \
    && dpkg -i "grafana_${GRAFANA_VERSION}_amd64.deb" \
    && rm "grafana_${GRAFANA_VERSION}_amd64.deb"

# ── Download Loki ───────────────────────────────────────────
RUN wget -q "https://github.com/grafana/loki/releases/download/v${LOKI_VERSION}/loki-linux-amd64.zip" \
    && unzip loki-linux-amd64.zip && mv loki-linux-amd64 /usr/local/bin/loki \
    && chmod +x /usr/local/bin/loki && rm loki-linux-amd64.zip

# ── Download Tempo ──────────────────────────────────────────
RUN wget -q "https://github.com/grafana/tempo/releases/download/v${TEMPO_VERSION}/tempo_${TEMPO_VERSION}_linux_amd64.deb" \
    && dpkg -i "tempo_${TEMPO_VERSION}_linux_amd64.deb" \
    && rm "tempo_${TEMPO_VERSION}_linux_amd64.deb"

# ── Download Prometheus ─────────────────────────────────────
RUN wget -q "https://github.com/prometheus/prometheus/releases/download/v${PROMETHEUS_VERSION}/prometheus-${PROMETHEUS_VERSION}.linux-amd64.tar.gz" \
    && tar xzf "prometheus-${PROMETHEUS_VERSION}.linux-amd64.tar.gz" \
    && mv "prometheus-${PROMETHEUS_VERSION}.linux-amd64/prometheus" /usr/local/bin/ \
    && mv "prometheus-${PROMETHEUS_VERSION}.linux-amd64/promtool" /usr/local/bin/ \
    && rm -rf "prometheus-${PROMETHEUS_VERSION}.linux-amd64"*

# ── Download OTEL Collector ─────────────────────────────────
RUN wget -q "https://github.com/open-telemetry/opentelemetry-collector-releases/releases/download/v${OTEL_VERSION}/otelcol-contrib_${OTEL_VERSION}_linux_amd64.deb" \
    && dpkg -i "otelcol-contrib_${OTEL_VERSION}_linux_amd64.deb" \
    && rm "otelcol-contrib_${OTEL_VERSION}_linux_amd64.deb"

# ── Create data directories ─────────────────────────────────
RUN mkdir -p /data/grafana /data/loki /data/tempo /data/prometheus /data/otel \
    && chown -R grafana:grafana /data/grafana

# ── Copy configuration files ────────────────────────────────
COPY configs/supervisord.conf /etc/supervisor/conf.d/observability.conf
# Configs with env var placeholders go as .tmpl — entrypoint runs envsubst
COPY configs/loki-prod.yml /etc/loki/loki.yml.tmpl
COPY configs/tempo-prod.yml /etc/tempo/tempo.yml.tmpl
COPY configs/prometheus-prod.yml /etc/prometheus/prometheus.yml.tmpl
COPY configs/alerting-rules.yml /etc/prometheus/alerting-rules.yml
COPY configs/otel-collector-prod.yml /etc/otelcol-contrib/config.yaml
COPY configs/nginx.conf /etc/nginx/nginx.conf
COPY configs/grafana-datasources.yml /etc/grafana/provisioning/datasources/datasources.yml
COPY configs/grafana-dashboards.yml /etc/grafana/provisioning/dashboards/dashboards.yml
COPY dashboards/ /var/lib/grafana/dashboards/
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# ── Grafana config overrides (port 3001 — nginx fronts port 3000) ──
RUN sed -i 's|;http_port = 3000|http_port = 3001|' /etc/grafana/grafana.ini \
    && sed -i 's|;data = /var/lib/grafana|data = /data/grafana|' /etc/grafana/grafana.ini \
    && sed -i 's|;provisioning = conf/provisioning|provisioning = /etc/grafana/provisioning|' /etc/grafana/grafana.ini

# ── Expose ports ────────────────────────────────────────────
# 3000 = nginx (reverse proxy: Grafana + OTLP HTTP + Loki)
EXPOSE 3000

# ── Health check ────────────────────────────────────────────
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -sf http://localhost:3000/healthz || exit 1

CMD ["/entrypoint.sh"]
