FROM python:3.12-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends git sqlite3 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /bin/sh bench

WORKDIR /work
USER bench
