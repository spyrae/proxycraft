# MTProto Runtime Config

Этот документ фиксирует текущую production-схему MTProto в `proxycraft`.

## Цель

У MTProto не должно быть зависимости от ручного редактирования host-файлов или от разъезда между:

- runtime-конфигом контейнера;
- ссылками, которые выдаёт backend пользователю;
- активными подписками в базе.

## Источник истины

Статические параметры MTProto берутся из `Config` / `.env`:

- `SHOP_MTPROTO_HOST`
- `SHOP_MTPROTO_PORT`
- `SHOP_MTPROTO_CONFIG_PATH`
- `SHOP_MTPROTO_TLS_DOMAIN`
- `SHOP_MTPROTO_MASK_HOST`
- `SHOP_MTPROTO_MASK_PORT`
- `SHOP_MTPROTO_FAST_MODE`

Динамическая часть (`USERS`) строится из активных записей в `proxycraft_mtproto_subscriptions`.

## Runtime lifecycle

1. `MTProtoService.sync_runtime_config()` собирает активные подписки из БД.
2. На их основе полностью рендерится `mtproto/config.py`.
3. Если содержимое изменилось, бот отправляет `SIGUSR2` в `proxycraft-mtproto`.
4. Этот же sync вызывается:
   - на startup бота;
   - после активации MTProto подписки;
   - после деактивации;
   - после cleanup истёкших подписок.

## Ожидаемый формат config.py

Конфиг рендерится в детерминированном виде:

- `PORT`
- `USERS`
- `TLS_DOMAIN`
- `MASK = True`
- `MASK_HOST`
- `MASK_PORT`
- `FAST_MODE`
- `MODES = {"classic": False, "secure": False, "tls": True}`

Это означает, что production использует только FakeTLS mode, и клиентские ссылки должны кодировать тот же `TLS_DOMAIN`.

## Infra guarantees

- `proxycraft-mtproto` собирается из pinned upstream image build, а не из отсутствующего host script.
- `cryptography` pinned по версии в Docker build.
- `config.py` монтируется в MTProto контейнер в read-only режиме.
- у MTProto есть container healthcheck на локальный порт `8444`.
- production workflow удаляет только зависшие временные compose-контейнеры `bot` / `mtproto` перед recreate.
