FROM python:3.10-slim

ARG MTPROTO_PROXY_VERSION=v1.1.1
ARG CRYPTOGRAPHY_VERSION=46.0.5

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Pin the upstream MTProto proxy version at build time so deploys stay reproducible.
RUN curl -fsSL "https://github.com/alexbers/mtprotoproxy/archive/refs/tags/${MTPROTO_PROXY_VERSION}.tar.gz" -o /tmp/mtprotoproxy.tar.gz \
    && tar -xzf /tmp/mtprotoproxy.tar.gz -C /tmp \
    && cp -R /tmp/mtprotoproxy-${MTPROTO_PROXY_VERSION#v}/. /app/ \
    && rm -rf /tmp/mtprotoproxy.tar.gz /tmp/mtprotoproxy-${MTPROTO_PROXY_VERSION#v} \
    && pip install --no-cache-dir "cryptography==${CRYPTOGRAPHY_VERSION}" \
    && mkdir -p /opt/mtproto-defaults /app/runtime \
    && cp /app/config.py /opt/mtproto-defaults/config.py \
    && useradd --create-home --home-dir /app --shell /usr/sbin/nologin mtproxy \
    && chown -R mtproxy:mtproxy /app /opt/mtproto-defaults

COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

EXPOSE 8444

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
