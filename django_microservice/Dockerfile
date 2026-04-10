FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir poetry

COPY pyproject.toml poetry.lock* /app/
RUN poetry config virtualenvs.create false \
 && poetry install --no-interaction --no-ansi --no-root

COPY . /app

ENV PYTHONUNBUFFERED=1
ENV DJANGO_SETTINGS_MODULE=core.settings

CMD ["sh", "-c", "python manage.py migrate --noinput && uvicorn core.asgi:application --host 0.0.0.0 --port 8000"]
