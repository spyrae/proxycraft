FROM python:3.12-slim-bullseye

ENV PYTHONPATH=/

RUN apt-get update && apt-get install -y --no-install-recommends wireguard-tools curl ca-certificates && \
    curl -fsSL https://download.docker.com/linux/static/stable/x86_64/docker-27.5.1.tgz | tar xz --strip-components=1 -C /usr/local/bin docker/docker && \
    rm -rf /var/lib/apt/lists/*

COPY pyproject.toml /
RUN pip install poetry && poetry install

COPY ./app /app
COPY ./scripts /app/scripts
RUN poetry run pybabel compile -d /app/locales -D bot
