FROM python:3.12-slim

ARG MTPROTO_PROXY_VERSION=v1.0.7

ENV PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Pin the upstream MTProto proxy version at build time so deploys stay reproducible.
RUN curl -fsSL "https://github.com/alexbers/mtprotoproxy/archive/refs/tags/${MTPROTO_PROXY_VERSION}.tar.gz" -o /tmp/mtprotoproxy.tar.gz \
    && tar -xzf /tmp/mtprotoproxy.tar.gz -C /tmp \
    && cp -R /tmp/mtprotoproxy-${MTPROTO_PROXY_VERSION#v}/. /app/ \
    && rm -rf /tmp/mtprotoproxy.tar.gz /tmp/mtprotoproxy-${MTPROTO_PROXY_VERSION#v} \
    && pip install --no-cache-dir cryptography

EXPOSE 8444

CMD ["python", "mtprotoproxy.py"]
