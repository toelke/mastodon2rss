FROM python:3.12-slim AS python-base
WORKDIR /app
COPY ./requirements.txt /app
RUN pip install --no-cache-dir -r requirements.txt
COPY main.py /app

EXPOSE 12345
WORKDIR /data
ENV PYTHONUNBUFFERED=1
ENV OWN_MASTODON_INSTANCE https://example.com/
ENV PUBLIC_URL https://example.com/
ENTRYPOINT ["python3", "/app/main.py"]
