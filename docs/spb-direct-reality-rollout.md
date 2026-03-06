# Saint Petersburg Direct REALITY Rollout

Этот документ описывает целевую схему для локации `Saint Petersburg`.
`Amsterdam` не меняется и продолжает работать на текущем профиле по умолчанию.

## Что изменено в коде

Для серверов появились per-server overrides:

- `subscription_host`
- `subscription_port`
- `subscription_path`
- `inbound_remark`
- `client_flow`

Если эти поля не заполнены, backend использует старые глобальные `XUI_*` значения.
Это означает:

- `Amsterdam` продолжает работать как раньше;
- `Saint Petersburg` можно перевести на отдельный direct REALITY профиль без влияния на остальные локации.

## Целевая схема для SPB

```text
Client -> Direct TCP 443 -> Xray VLESS + REALITY + XTLS Vision
```

Без Cloudflare proxy path и без WebSocket.

## Что нужно создать на сервере SPB

В `3X-UI/Xray` должен появиться отдельный inbound для SPB:

- protocol: `vless`
- port: `443`
- transport: `raw`
- security: `reality`
- flow: `xtls-rprx-vision`
- clients: managed by bot via 3X-UI API

Рекомендованные параметры профиля:

- отдельный hostname для SPB direct access;
- отдельный inbound remark, например `spb-reality`;
- отдельный public host для subscription, если панель и клиентский endpoint должны расходиться.

## Что заполнить в admin UI для SPB

Открыть `Admin -> Servers -> Configure` у сервера `Saint Petersburg`.

Заполнить:

- `Panel host`
  Используется ботом для входа в `3X-UI API`.
  Пример: `https://panel-spb.example.com`

- `Location`
  Должно оставаться `Saint Petersburg`

- `Subscription host`
  Публичный host, который будет использоваться для subscription URL.
  Пример: `https://spb.example.com`

- `Subscription port`
  Обычно `443`

- `Subscription path`
  Обычно `/user/`

- `Inbound remark`
  Должен совпадать с REALITY inbound в `3X-UI`.
  Пример: `spb-reality`

- `Client flow`
  `xtls-rprx-vision`

## Ожидаемое поведение после настройки

- новые пользователи SPB получают клиентов в SPB REALITY inbound;
- ключи для SPB строятся из server-specific subscription endpoint;
- Amsterdam продолжает использовать старые глобальные настройки;
- при смене `Panel host` backend переинициализирует соединение с 3X-UI.

## Checklist после выката

1. Применить Alembic migration `008_add_server_transport_overrides`.
2. Задеплоить backend.
3. В admin UI заполнить server-specific поля только для `Saint Petersburg`.
4. Проверить создание нового VPN клиента с локацией `Saint Petersburg`.
5. Проверить, что subscription URL для SPB использует новый endpoint.
6. Проверить, что `Amsterdam` создаёт клиентов по старому профилю.

## Smoke test для SPB

Проверить с новым пользователем:

1. покупка или trial с локацией `Saint Petersburg`;
2. успешное создание клиента в правильном inbound;
3. импорт subscription в клиент;
4. открытие нескольких RU сайтов, включая проблемные;
5. latency и throughput из Индонезии.
