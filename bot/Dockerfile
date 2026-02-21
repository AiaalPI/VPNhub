FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_DEFAULT_TIMEOUT=120
ENV PIP_RETRIES=10
ENV PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        wget \
        build-essential \
        postgresql-client \
    && rm -rf /var/lib/apt/lists/*

COPY bot/requirements.txt /app/requirements.txt

RUN pip install --no-cache-dir --retries 10 --timeout 120 -U pip setuptools==70.1 wheel
RUN pip install --no-cache-dir --retries 10 --timeout 120 -r /app/requirements.txt
RUN apt-get update && \
    apt-get purge -y --auto-remove build-essential && \
    rm -rf /var/lib/apt/lists/*

COPY bot/ /app/
COPY wait-for-services.sh /app/wait-for-services.sh
RUN chmod +x /app/wait-for-services.sh

CMD ["bash", "-lc", "/app/wait-for-services.sh && python -m run"]
