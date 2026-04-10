# Инструкция по развёртыванию

Пошаговое руководство по развёртыванию стенда для сравнительного бенчмарка Python веб-фреймворков.

## 1. Аппаратные требования

| Параметр | Минимум | Рекомендуемо |
|----------|---------|--------------|
| CPU | 2 ядра | 4+ ядер |
| RAM | 4 GB | 8+ GB |
| Диск | 10 GB свободно | 20 GB |
| Сеть | Localhost (без внешнего доступа) | — |

> Для корректных результатов бенчмарка рекомендуется выделенная машина без фоновой нагрузки (антивирус, браузеры, IDE). Виртуальные машины и WSL2 вносят дополнительные накладные расходы.

## 2. Программные требования

| Компонент | Версия | Проверка |
|-----------|--------|----------|
| ОС | Linux (Ubuntu 22.04+), macOS 13+, Windows 10/11 с WSL2 | `uname -a` |
| Docker Engine | 24.0+ | `docker --version` |
| Docker Compose | v2.20+ (плагин) | `docker compose version` |
| Python | 3.12+ | `python --version` |
| Poetry | 1.8+ | `poetry --version` |
| Git | 2.40+ | `git --version` |
| curl | любая | `curl --version` |

### Установка зависимостей (Ubuntu)

```bash
# Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# Python 3.12
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt install python3.12 python3.12-venv

# Poetry
curl -sSL https://install.python-poetry.org | python3 -

# Проверка
docker --version
docker compose version
python3.12 --version
poetry --version
```

## 3. Клонирование репозитория

```bash
git clone <URL_РЕПОЗИТОРИЯ> itmo_practics
cd itmo_practics
```

## 4. Развёртывание всех сервисов

### 4.1. Запуск одной командой

```bash
# Linux / macOS
chmod +x start_all.sh
./start_all.sh

# Windows (PowerShell)
.\start_all.ps1
```

### 4.2. Запуск вручную (по одному)

```bash
# Django (API: localhost:8000, DB: localhost:5433)
cd django_microservice
docker compose up -d --build

# FastAPI (API: localhost:8001, DB: localhost:5433)
cd ../fastapi_microservice
docker compose up -d --build

# Litestar (API: localhost:8002, DB: localhost:5434)
cd ../litestar_microservice
docker compose up -d --build

# Robyn (API: localhost:8003, DB: localhost:5435)
cd ../robyn_microservice
docker compose up -d --build
```

### 4.3. Карта портов

| Сервис | API | PostgreSQL |
|--------|-----|------------|
| Django | `localhost:8000` | `localhost:5433` |
| FastAPI | `localhost:8001` | `localhost:5433` |
| Litestar | `localhost:8002` | `localhost:5434` |
| Robyn | `localhost:8003` | `localhost:5435` |

## 5. Проверка работоспособности

После запуска убедитесь, что все 4 сервиса отвечают:

```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/users/   # Django   → 200
curl -s -o /dev/null -w "%{http_code}" http://localhost:8001/api/users/   # FastAPI  → 200
curl -s -o /dev/null -w "%{http_code}" http://localhost:8002/api/users/   # Litestar → 200
curl -s -o /dev/null -w "%{http_code}" http://localhost:8003/api/users/   # Robyn    → 200
```

Или одной командой:

```bash
for port in 8000 8001 8002 8003; do
  echo -n "localhost:$port → "
  curl -sf http://localhost:$port/api/users/ > /dev/null && echo "OK" || echo "FAIL"
done
```

## 6. Наполнение тестовыми данными

Скрипт `seed_all.py` заполняет все 4 базы идентичными данными (seed=42):

```bash
# Установить psycopg (если ещё не установлен)
pip install psycopg[binary]

# Запустить сидирование
python seed_all.py
```

Результат:
- 1000 пользователей
- ~7500 заказов (5-10 на пользователя)
- Данные идентичны во всех 4 БД

## 7. Запуск тестов производительности

### 7.1. Pytest — latency и throughput

```bash
# Все сервисы одной командой
# Linux / macOS
./run_tests.sh

# Windows (PowerShell)
.\run_tests.ps1
```

Результаты сохраняются в `results/` и JSON-файлы внутри каждого микросервиса.

### 7.2. Locust — нагрузочное тестирование

```bash
cd django_microservice
locust -f locustfile.py --host=http://localhost:8000
# Web UI: http://localhost:8089
```

Повторить для каждого фреймворка, изменяя `--host` и порт.

## 8. Остановка сервисов

```bash
# Все сразу
# Linux / macOS
./stop_all.sh

# Windows (PowerShell)
.\stop_all.ps1

# Вручную (по одному)
cd django_microservice && docker compose down -v
cd ../fastapi_microservice && docker compose down -v
cd ../litestar_microservice && docker compose down -v
cd ../robyn_microservice && docker compose down -v
```

## 9. CI/CD

Проект использует GitVerse Actions для автоматической проверки при каждом push/PR.

Конфигурация: `.gitverse/workflows/ci.yaml`

Пайплайн выполняет:
1. **Lint** — проверка стиля кода (ruff) по всем 4 микросервисам
2. **Build** — сборка Docker-образов для каждого фреймворка
3. **Smoke Test** — запуск контейнеров и проверка HTTP-ответов (`GET /api/users/`, `POST /api/users/`)

Сборка запускается параллельно для всех 4 фреймворков (матричная стратегия).

## 10. Troubleshooting

### Контейнер не запускается

```bash
cd <microservice>_microservice
docker compose logs
```

### Порт уже занят

```bash
# Найти процесс
lsof -i :8000   # Linux/macOS
netstat -ano | findstr :8000   # Windows

# Изменить порт в docker-compose.yml
ports:
  - "9000:8000"   # внешний:внутренний
```

### БД не подключается при seed

Убедитесь, что контейнеры с PostgreSQL запущены:

```bash
docker ps --format "table {{.Names}}\t{{.Ports}}\t{{.Status}}"
```

### Медленная сборка образов

Первая сборка скачивает базовый образ `python:3.12-slim` (~150 MB) и устанавливает зависимости. Повторные сборки используют кеш Docker.

```bash
# Принудительная пересборка без кеша
docker compose build --no-cache
```
