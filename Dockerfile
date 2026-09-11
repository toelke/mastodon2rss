# Pinned to 3.13. Mastodon.py re-derives type hints for every attribute it sets
# while parsing API responses (https://github.com/halcy/Mastodon.py/issues/448),
# so parsing a home timeline costs seconds, not milliseconds. On 3.14 annotations
# are evaluated lazily (PEP 649/749), which roughly doubles that cost and pushes
# /feed past the 15s proxy timeout on our deployment host.
# smoke_test.py enforces this pin and will pass again once upstream is fixed.
FROM python:3.13-slim AS python-base

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app

# Copy project files
COPY pyproject.toml uv.lock /app/
COPY main.py /app/

# Install dependencies from pyproject.toml using uv
RUN uv sync --frozen --no-dev --no-install-project

# Fails the build if the base image moves to python 3.14 while Mastodon.py is
# still slow to parse API responses -- that combination makes /feed exceed the
# 15s proxy timeout. See smoke_test.py and the FROM line above.
COPY smoke_test.py /app/
RUN /app/.venv/bin/python /app/smoke_test.py

EXPOSE 12345
WORKDIR /data
ENV PYTHONUNBUFFERED=1
ENV OWN_MASTODON_INSTANCE=example.com
ENV PUBLIC_URL=https://example.com/
ENTRYPOINT ["/app/.venv/bin/python", "/app/main.py"]
