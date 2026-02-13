FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        wget gnupg ca-certificates \
        build-essential gcc \
        libssl-dev libffi-dev \
    && mkdir -p /etc/apt/keyrings \
    && wget -qO- https://www.postgresql.org/media/keys/ACCC4CF8.asc | gpg --dearmor -o /etc/apt/keyrings/postgresql.gpg \
    && . /etc/os-release \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/postgresql.gpg] http://apt.postgresql.org/pub/repos/apt ${VERSION_CODENAME}-pgdg main" > /etc/apt/sources.list.d/pgdg.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends postgresql-client-16 libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir -U pip setuptools==70.1 wheel
RUN pip install --no-cache-dir -r /app/requirements.txt

# убираем сборочные зависимости после установки питон-пакетов
RUN apt-get purge -y --auto-remove build-essential gcc libssl-dev libffi-dev \
    && rm -rf /var/lib/apt/lists/*

COPY run.py .
COPY wait-for-services.sh /app/wait-for-services.sh
COPY bot /app/bot
COPY alembic.ini .
RUN chmod +x /app/wait-for-services.sh

CMD ["/bin/sh", "-c", "/app/wait-for-services.sh && python -m run"]
