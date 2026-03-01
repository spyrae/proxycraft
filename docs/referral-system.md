# Referral System (RB-260)

Двухуровневая реферальная система с автоначислением бонусов за первый платёж.

## Команды бота

| Команда | Описание |
|---------|----------|
| `/ref` | Реферальная страница — ссылка, правила, накопленные бонусы |
| `/ref stats` | Детальная статистика — кол-во приглашённых, с оплатой, лимит |

Также доступна через inline-кнопку **"Пригласить"** в главном меню.

## Как работает

### Приглашение

1. Пользователь A отправляет свою реферальную ссылку (`https://t.me/bot?start=<tg_id>`)
2. Пользователь B переходит по ссылке → создаётся запись `Referral(referrer=A, referred=B)`
3. Каждый пользователь может иметь только одного реферера (unique constraint на `referred_tg_id`)

### Начисление бонусов (при первом платеже)

Когда приглашённый пользователь B совершает **первый** оплаченный платёж:

| Получатель | Бонус | Описание |
|-----------|-------|----------|
| **Реферер A** (level 1) | +30 дней | Прямой пригласитель |
| **Реферер уровня 2** | +3 дня | Тот, кто пригласил A |
| **Приглашённый B** | +7 дней | Бонус за первый платёж по реферальной ссылке |

Бонусы создаются как pending `ReferrerReward` записи и обрабатываются фоновым scheduler'ом каждые 15 минут.

### Ограничения

- **Только первый платёж:** повторные платежи приглашённого НЕ генерируют новые награды
- **Лимит 365 дней:** максимум накопленных реферальных бонусов на одного реферера. При превышении начисляется только остаток до лимита
- **Уведомления:** после обработки бонуса рефереру отправляется сообщение в Telegram

## Архитектура

```
Payment Gateway (_on_payment_succeeded)
    │
    ├─ Transaction.update(status=COMPLETED)
    │
    └─ ReferralService.add_referrers_rewards_on_payment()
         │
         ├─ Transaction.get_completed_count() > 1? → skip (не первый платёж)
         │
         ├─ ReferrerReward.get_total_rewards_sum() → проверка лимита 365 дн.
         │
         ├─ Create ReferrerReward (level 1, referrer)
         ├─ Create ReferrerReward (level 2, second referrer)
         └─ Create ReferrerReward (referred bonus, +7 days)
              │
              ▼
    APScheduler (каждые 15 мин)
         │
         └─ reward_pending_referrals_after_payment()
              │
              ├─ process_referrer_rewards_after_payment(reward)
              │    └─ vpn_service.process_bonus_days()
              │
              └─ bot.send_message() → уведомление рефереру
```

## Конфигурация

Переменные окружения (defaults в `app/config.py`):

| Переменная | Default | Описание |
|-----------|---------|----------|
| `SHOP_REFERRER_REWARD_ENABLED` | `True` | Включена ли реферальная система |
| `SHOP_REFERRED_REWARD_TYPE` | `days` | Тип награды (`days` / `money`) |
| `SHOP_REFERRER_LEVEL_ONE_PERIOD` | `30` | Дней за прямого реферала |
| `SHOP_REFERRER_LEVEL_TWO_PERIOD` | `3` | Дней за реферала 2-го уровня |
| `SHOP_REFERRED_TRIAL_PERIOD` | `7` | Бонус дней приглашённому |
| `SHOP_REFERRED_TRIAL_ENABLED` | `False` | Бесплатный trial по ссылке (кнопка "Получить подарок") |

Лимит 365 дней задан константой `REFERRER_MAX_REWARD_DAYS` в `app/bot/services/referral.py`.

## Ключевые файлы

| Файл | Роль |
|------|------|
| `app/bot/routers/referral/handler.py` | Хендлеры `/ref`, `/ref stats`, callback'и |
| `app/bot/services/referral.py` | Бизнес-логика начисления и обработки наград |
| `app/bot/tasks/referral.py` | Фоновый scheduler + уведомления |
| `app/db/models/referral.py` | Модель `Referral` (связь referrer ↔ referred) |
| `app/db/models/referrer_reward.py` | Модель `ReferrerReward` (история начислений) |
| `app/bot/payment_gateways/_gateway.py` | Точка входа — вызов после успешного платежа |

## Таблицы БД

### vpncraft_referrals

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | PK | |
| `referrer_tg_id` | FK → users | Кто пригласил |
| `referred_tg_id` | FK → users, UNIQUE | Кого пригласили |
| `created_at` | datetime | Когда создана связь |
| `referred_rewarded_at` | datetime? | Когда приглашённый получил trial |
| `referred_bonus_days` | int? | Сколько дней trial получил |

### vpncraft_referrer_rewards

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | PK | |
| `user_tg_id` | FK → users | Кто получает награду |
| `reward_type` | enum | `DAYS` / `MONEY` |
| `reward_level` | enum? | `FIRST_LEVEL` / `SECOND_LEVEL` / NULL (referred bonus) |
| `amount` | decimal | Количество дней или денег |
| `payment_id` | str | ID платежа-триггера |
| `created_at` | datetime | Когда создана |
| `rewarded_at` | datetime? | Когда обработана (NULL = pending) |

**Unique constraint:** `(user_tg_id, payment_id)` — предотвращает дублирование наград.
