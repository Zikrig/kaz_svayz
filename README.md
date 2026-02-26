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
- CRUD API для всех таблиц БД

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

После запуска API доступно:
- Swagger UI: `http://localhost:8000/docs`
- OpenAPI JSON: `http://localhost:8000/openapi.json`

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

## CRUD API

Реализован полный CRUD для таблиц:
- `users`
- `requests` (таблица `supply_requests`)
- `responses` (таблица `supplier_responses`)

Эндпоинты на каждую сущность:
- `GET /<entity>` — список (с `limit`, `offset`)
- `GET /<entity>/{id}` — одна запись
- `POST /<entity>` — создание
- `PUT /<entity>/{id}` — полная замена
- `PATCH /<entity>/{id}` — частичное изменение
- `DELETE /<entity>/{id}` — удаление

Если в `.env` задан `API_TOKEN`, API требует заголовок:
- `x-api-key: <API_TOKEN>`

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
