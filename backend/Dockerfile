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
COPY requirements.lock ./
COPY zgrader ./zgrader
COPY alembic.ini ./
COPY alembic ./alembic

# Dependencies come from the lock, pinned and hash-checked; the package itself
# then installs with --no-deps so it cannot re-resolve anything behind the
# lock's back.
#
# --require-hashes is the part that does the work. Without it the lock is a
# suggestion: pip would happily accept a rebuilt artefact at the same version.
# With it, a mismatch fails the build rather than shipping quietly.
#
# Before this, `pip install .` resolved unbounded `>=` ranges at build time, so
# every rebuild picked up the newest release of everything -- including
# opencv-python-headless, pillow and weasyprint, which parse bytes uploaded by
# strangers. Behaviour could change with no commit behind it, and no past build
# could be reproduced to bisect against.
#
# Regenerate with the command in AGENTS.md -- it must be cross-resolved for
# linux/3.11, because uvicorn[standard] pulls uvloop and httptools only on
# non-Windows and a lock made on a Windows host silently omits them.
RUN pip install --no-cache-dir --require-hashes -r requirements.lock \
    && pip install --no-cache-dir --no-deps .

# Bind mount targets for scans/reports -- see docker-compose.yml volumes.
RUN mkdir -p /data/scans /data/reports

# Run as a non-root user so customer scans don't land root-owned on the host.
# UID/GID 99:100 is Unraid's `nobody:users`, which is what the bind-mounted
# scans directory is owned by there -- override with a build arg on other
# hosts, or the container won't be able to write to the mount.
ARG APP_UID=99
ARG APP_GID=100
RUN groupadd -g "${APP_GID}" -o app \
    && useradd -u "${APP_UID}" -g "${APP_GID}" -o -m -s /usr/sbin/nologin app \
    && chown -R "${APP_UID}:${APP_GID}" /app /data
USER app

EXPOSE 8000

# --proxy-headers/--forwarded-allow-ips: behind Caddy and the Cloudflare
# tunnel, every request otherwise appears to come from the proxy, which would
# put all users in one rate-limit bucket. Safe only because the origin is not
# directly reachable -- see infra/caddy/Caddyfile.
CMD ["uvicorn", "zgrader.api.main:app", "--host", "0.0.0.0", "--port", "8000", \
     "--proxy-headers", "--forwarded-allow-ips", "*"]
