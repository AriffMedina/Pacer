# Imagen de la aplicación. `docker compose up` levanta esto más Postgres, que
# es el primero de los cuatro criterios de entrega: el sistema completo desde
# cero en una máquina limpia.

FROM python:3.13-slim AS base

# uv desde su imagen oficial: no hace falta pip ni compilar nada.
COPY --from=ghcr.io/astral-sh/uv:0.12.5 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8

WORKDIR /app

# Las dependencias en su propia capa: cambiar código no reinstala el mundo.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY pacer/ ./pacer/
COPY web/ ./web/
RUN uv sync --frozen --no-dev

# Sin root. No necesita privilegios para servir HTTP.
RUN useradd --create-home --uid 1000 pacer && chown -R pacer:pacer /app
USER pacer

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

# Sin --reload: en un contenedor eso vigila archivos que nadie va a editar.
CMD ["uvicorn", "pacer.interfaces.http.app:app", "--host", "0.0.0.0", "--port", "8000"]
