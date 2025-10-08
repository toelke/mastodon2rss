FROM python:3.14-slim AS python-base

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app

# Copy project files
COPY pyproject.toml uv.lock /app/
COPY main.py /app/

# Install dependencies from pyproject.toml using uv
RUN uv sync --frozen --no-dev --no-install-project

EXPOSE 12345
WORKDIR /data
ENV PYTHONUNBUFFERED=1
ENV OWN_MASTODON_INSTANCE=example.com
ENV PUBLIC_URL=https://example.com/
ENTRYPOINT ["/app/.venv/bin/python", "/app/main.py"]
