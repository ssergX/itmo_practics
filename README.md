# Сравнительный анализ Python веб-фреймворков

> Выпускная квалификационная работа, ИТМО 2026 — бенчмарк Django, FastAPI, Litestar и Robyn на идентичном REST API

## Архитектура

Четыре независимых микросервиса с **одинаковой бизнес-логикой** (Users + Orders), различающихся только фреймворком и стеком сериализации:

```
itmo_practics/
├── django_microservice/      Django 6.0 + DRF + adrf (async)
├── fastapi_microservice/     FastAPI 0.115 + Pydantic v2
├── litestar_microservice/    Litestar 2.15 + msgspec
└── robyn_microservice/       Robyn 0.63 + orjson (Rust runtime)
```

Каждый сервис поднимается в Docker с собственной PostgreSQL 16 и отдаёт одинаковые эндпоинты.

## Стек

| | Django | FastAPI | Litestar | Robyn |
|---|---|---|---|---|
| **Фреймворк** | Django 6.0 + DRF | FastAPI 0.115 | Litestar 2.15 | Robyn 0.63 |
| **Runtime** | Python (Uvicorn) | Python (Uvicorn) | Python (Uvicorn) | Rust (actix) |
| **Async** | adrf + Django async ORM | нативный | нативный | нативный |
| **ORM** | Django ORM | SQLAlchemy 2.0 async | SQLAlchemy 2.0 async | SQLAlchemy 2.0 async |
| **Сериализация** | orjson (ручная) | Pydantic v2 | msgspec | orjson (ручная) |
| **БД-драйвер** | psycopg3 + pool | asyncpg | asyncpg | asyncpg |
| **ASGI/HTTP сервер** | Uvicorn | Uvicorn | Uvicorn | встроенный (Rust) |
| **Python** | 3.12 | 3.12 | 3.12 | 3.12 |

## API

Все четыре сервиса реализуют идентичные эндпоинты:

| Метод | Путь | Описание |
|---|---|---|
| `GET` | `/api/users/` | Список пользователей с вложенными заказами |
| `POST` | `/api/users/` | Создание пользователя |
| `POST` | `/api/orders/` | Создание заказа |

**GET /api/users/** — основной read-heavy эндпоинт для бенчмарка. Возвращает ~1000 пользователей с ~7500 вложенными заказами.

## Быстрый старт

### Требования

- Docker + Docker Compose
- Python 3.12+
- Poetry

### Запуск всех четырёх сервисов

```bash
# Django (порт 8000)
cd django_microservice
docker-compose up -d --build

# FastAPI (порт 8001)
cd ../fastapi_microservice
docker-compose up -d --build

# Litestar (порт 8002)
cd ../litestar_microservice
docker-compose up -d --build

# Robyn (порт 8003)
cd ../robyn_microservice
docker-compose up -d --build
```

### Наполнение тестовыми данными

```bash
# Django — management-команда
cd django_microservice
docker-compose exec api python manage.py seed_db

# FastAPI / Litestar / Robyn — таблицы создаются автоматически при старте,
# для seed используйте Locust (create_user + create_order задачи)
```

## Порты

| Сервис | API | PostgreSQL |
|---|---|---|
| Django | `localhost:8000` | `localhost:5433` |
| FastAPI | `localhost:8001` | `localhost:5433` |
| Litestar | `localhost:8002` | `localhost:5434` |
| Robyn | `localhost:8003` | `localhost:5435` |

## Тестирование

### Pytest — latency и throughput

```bash
# Django
cd django_microservice
pytest tests/test_latency.py tests/test_throughput.py -v

# FastAPI
cd fastapi_microservice
pytest app/tests/test_latency.py app/tests/test_throughput.py -v

# Litestar
cd litestar_microservice
pytest app/tests/test_latency.py app/tests/test_throughput.py -v

# Robyn
cd robyn_microservice
pytest app/tests/test_latency.py app/tests/test_throughput.py -v
```

Результаты сохраняются в JSON-файлы (`latency_users_*.json`, `throughput_users_*.json`).

### Locust — нагрузочное тестирование

```bash
# Django
cd django_microservice
locust -f locustfile.py --host=http://localhost:8000

# FastAPI
cd fastapi_microservice
locust -f locustfile.py --host=http://localhost:8001

# Litestar
cd litestar_microservice
locust -f locustfile.py --host=http://localhost:8002

# Robyn
cd robyn_microservice
locust -f locustfile.py --host=http://localhost:8003
```

Web UI Locust: [http://localhost:8089](http://localhost:8089)

## Метрики

Каждый сервис логирует per-request метрики через psutil:

- **elapsed_ms** — время обработки запроса
- **cpu_percent** — загрузка CPU процессом
- **ram_mb** — потребление памяти (RSS)
- **threads** — количество потоков

## Что измеряется

| Метрика | Инструмент | Описание |
|---|---|---|
| Avg / P50 / P95 / P99 latency | pytest + httpx | 50 последовательных GET-запросов |
| Throughput (RPS) | pytest + httpx | 200 запросов, concurrency 20 |
| Latency под нагрузкой | Locust | Настраиваемое кол-во пользователей |
| CPU / RAM / Threads | psutil middleware | Per-request мониторинг |

## Структура проекта

```
django_microservice/
├── app/                  # Django-приложение (models, views, urls)
│   └── management/       # seed_db команда
├── core/                 # Django settings, urls, asgi
├── tests/                # pytest: latency, throughput, flow
├── locustfile.py
├── Dockerfile
└── docker-compose.yml

fastapi_microservice/
├── app/
│   ├── main.py           # FastAPI app + роуты
│   ├── models.py         # SQLAlchemy модели
│   ├── schemas.py        # Pydantic v2 схемы
│   ├── crud.py           # CRUD-операции
│   ├── db.py             # engine + session
│   ├── monitoring.py     # psutil метрики
│   └── tests/
├── locustfile.py
├── Dockerfile
└── docker-compose.yml

litestar_microservice/
├── app/
│   ├── main.py           # Litestar app + роуты
│   ├── models.py         # SQLAlchemy модели
│   ├── schemas.py        # msgspec схемы
│   ├── crud.py           # CRUD-операции
│   ├── db.py             # engine + session
│   ├── monitoring.py     # psutil метрики
│   └── tests/
├── locustfile.py
├── Dockerfile
└── docker-compose.yml

robyn_microservice/
├── app/
│   ├── main.py           # Robyn app + роуты (Rust runtime)
│   ├── models.py         # SQLAlchemy модели
│   ├── crud.py           # CRUD-операции
│   ├── db.py             # engine + session
│   ├── monitoring.py     # psutil метрики
│   └── tests/
├── locustfile.py
├── Dockerfile
└── docker-compose.yml
```

## Оптимизации Django

Для честного сравнения Django оптимизирован до production-уровня:

- **Middleware** — сокращён до 1 (убраны sessions, CSRF, auth, messages, clickjacking)
- **Сериализация** — orjson вместо DRF Response + json.dumps
- **ORM** — `.values()` вместо создания Model-объектов
- **Connection pool** — psycopg3 native pool
- **DEBUG = False** — отключён SQL-логгинг

## CI/CD

Проект использует **GitVerse Actions** для автоматической проверки при каждом push и pull request.

| Этап | Что делает |
|------|-----------|
| **Lint** | Проверка стиля кода (ruff) по всем 4 микросервисам |
| **Build & Smoke Test** | Сборка Docker-образов + запуск контейнеров + HTTP smoke-тесты (`GET /api/users/`, `POST /api/users/`) |

Сборка выполняется параллельно для всех фреймворков (матричная стратегия).

Конфигурация: [`.gitverse/workflows/ci.yaml`](.gitverse/workflows/ci.yaml)

## Развёртывание

Полная пошаговая инструкция по развёртыванию с аппаратными и программными требованиями: **[DEPLOYMENT.md](DEPLOYMENT.md)**

## Лицензия

Выпускная квалификационная работа, ИТМО 2026.
