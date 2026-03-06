# ADR-001: Self-Contained WhatsApp Proxy Runtime

## Status

Accepted

## Date

2026-03-06

## Context

`WhatsApp Proxy` в production был завязан на внешний host-mounted сертификат
`/etc/haproxy/ssl/proxy.pem`, который не поставлялся кодом и не управлялся через
репозиторий. Из-за этого `HAProxy` падал на старте, а сервис оставался в
сломленном состоянии до ручного вмешательства на сервере.

Дополнительно runtime-путь обновления конфигурации был небезопасным:

- `haproxy.cfg` перезаписывался неатомарно;
- бот делал blind reload без валидации конфигурации внутри контейнера;
- production deploy не собирал `whatsapp` как собственный image;
- healthcheck не проверял реальный runtime-path сервиса.

## Decision

`WhatsApp Proxy` переводится на self-contained runtime-модель:

1. Сервис собирается как отдельный Docker image из `whatsapp/Dockerfile`.
2. TLS bootstrap выполняется внутри контейнера через `docker-entrypoint.sh`.
3. Сертификат больше не зависит от файлов на хосте и хранится в named volume.
4. `HAProxy` конфигурация пишется ботом атомарно.
5. Перед reload бот валидирует конфигурацию внутри контейнера через Docker socket.
6. Reload выполняется через сигнал контейнерному entrypoint, который запускает
   graceful `HAProxy -sf` reload и не принимает битую конфигурацию.
7. В production deploy `whatsapp` собирается и поднимается так же, как `bot` и
   `mtproto`.

## Consequences

### Positive

- Production runtime стал воспроизводимым и не зависит от ручных файлов.
- Broken TLS-materials больше не могут silently сломать `HAProxy`.
- Изменения подписок теперь проходят через validate-before-reload path.
- Health status сервиса отражает реальное состояние runtime.

### Trade-offs

- Runtime стал чуть сложнее за счёт entrypoint-supervisor логики.
- TLS CN теперь должен управляться через env при необходимости кастомизации.

## Follow-up

- Добавить post-deploy synthetic check для внешнего клиентского frontend-порта.
- Вынести отдельный smoke-runner для `VPN / MTProto / WhatsApp`.
