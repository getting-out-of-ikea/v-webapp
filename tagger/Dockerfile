# syntax=docker/dockerfile:1
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PYTHONUNBUFFERED=1

WORKDIR /app

# 1. Dipendenze di runtime in uno strato separato dal codice applicativo:
#    cambiare solo il codice non forza il reinstall delle dipendenze.
COPY pyproject.toml uv.lock .python-version README.md ./
RUN uv sync --frozen --no-dev --no-install-project

# 2. Codice applicativo e installazione del pacchetto stesso.
COPY src ./src
RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

CMD ["uvicorn", "tagger.main:app", "--host", "0.0.0.0", "--port", "8000"]
