FROM python:3.12-slim-bullseye

ENV PYTHONPATH=/

RUN apt-get update && apt-get install -y --no-install-recommends wireguard-tools && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml /
RUN pip install poetry && poetry install

COPY ./app /app
COPY ./scripts /app/scripts
RUN poetry run pybabel compile -d /app/locales -D bot
