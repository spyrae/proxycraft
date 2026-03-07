FROM haproxy:2.9-alpine

USER root

RUN apk add --no-cache openssl netcat-openbsd

COPY haproxy.cfg /opt/proxycraft-defaults/haproxy.cfg
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
COPY healthcheck.sh /usr/local/bin/healthcheck.sh

RUN chmod +x /usr/local/bin/docker-entrypoint.sh /usr/local/bin/healthcheck.sh

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
