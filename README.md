# Telegram бот-агрегатор (aiogram + Docker)

Готовый MVP бота под ваше ТЗ:
- роли: `consumer`, `supplier`, `admin`
- регистрация с подтверждением телефона (inline)
- потребитель: создание заявки, мои заявки, просмотр откликов, остановка откликов
- поставщик: лента заявок, отклик на заявку, мои отклики
- очередь уведомлений, пока пользователь в контекстном процессе
- авто-таймаут процесса (5 минут для потребителя, 10 минут для поставщика)
- админка: статистика, назначение роли, рассылка
- счетчик заявок пользователя в `users.sent_requests_count`

## Стек

- Python 3.11
- aiogram 3
- SQLAlchemy async
- SQLite (через `aiosqlite`)
- Docker / docker-compose

## Быстрый старт

1. Скопируйте `.env.example` в `.env`
2. Заполните `BOT_TOKEN` и `ADMIN_IDS`
3. Запустите:

```bash
docker compose up --build
```

## Локальный запуск (без Docker)

```bash
python -m venv .venv
. .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m app.main
```

## Inline-кнопки

Все основные действия сделаны через inline-кнопки:
- подтверждение номера
- меню ролей
- подтверждение/изменение/отмена заявок
- отклик поставщика
- просмотр откликов и контакт
- админ-панель

## Что можно расширить дальше

- добавить миграции Alembic
- вынести очередь уведомлений из памяти в БД/Redis
- ввести RBAC и аудит действий админа
- добавить анти-спам/лимиты и rate limiting
- подключить Sentry/Prometheus

## Структура

- `app/main.py` — запуск и polling
- `app/handlers.py` — все роуты (FSM + callbacks)
- `app/services.py` — очереди, таймауты, форматирование и уведомления
- `app/models.py` — модели БД
- `app/keyboards.py` — inline клавиатуры
- `app/states.py` — FSM состояния
- `app/config.py` — env-конфиг
- `app/db.py` — подключение и сессии БД
