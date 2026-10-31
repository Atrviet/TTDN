FROM python:3.11-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    VIRTUAL_ENV=/opt/venv

RUN python -m venv "$VIRTUAL_ENV"
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
COPY requirements.txt .
ARG TORCH_VERSION=2.9.1
RUN pip install --upgrade pip \
    && pip install "torch==$TORCH_VERSION" --index-url https://download.pytorch.org/whl/cpu \
    && pip install -r requirements.txt

FROM python:3.11-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH" \
    HF_HOME=/home/app/.cache/huggingface

RUN apt-get update \
    && apt-get install --no-install-recommends -y curl libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --create-home app

WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY --chown=app:app alembic.ini ./
COPY --chown=app:app alembic ./alembic
COPY --chown=app:app app ./app
COPY --chown=app:app scripts/docker-entrypoint.sh /usr/local/bin/docker-entrypoint
RUN chmod 0755 /usr/local/bin/docker-entrypoint \
    && mkdir -p /data/documents /data/chroma "$HF_HOME" \
    && chown -R app:app /data /home/app

USER app
EXPOSE 8000
ENTRYPOINT ["docker-entrypoint"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips=*"]
