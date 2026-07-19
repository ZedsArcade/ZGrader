# Single image for both the API (uvicorn) and the watcher worker -- they
# share the same codebase and dependencies, and only differ in entrypoint
# (see docker-compose.yml's `command:` overrides). opencv-python-headless
# bundles its own shared libs (manylinux wheel repair), so the only system
# packages needed here are WeasyPrint's -- it renders PDFs via Pango/Cairo,
# which don't ship inside the wheel.
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libpangoft2-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    libharfbuzz0b \
    libfribidi0 \
    fontconfig \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml ./
COPY zgrader ./zgrader
COPY alembic.ini ./
COPY alembic ./alembic

RUN pip install --no-cache-dir .

# Bind mount targets for scans/reports -- see docker-compose.yml volumes.
RUN mkdir -p /data/scans /data/reports

EXPOSE 8000

CMD ["uvicorn", "zgrader.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
