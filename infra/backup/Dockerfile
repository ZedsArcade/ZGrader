# The backup service's script, baked in rather than bind-mounted.
#
# It was a single-file bind mount first, and that fails badly: if the source
# path is momentarily absent when the container starts -- a stack deployed
# before the repo finished updating, a fresh checkout, a moved stack directory
# -- Docker *creates* the missing source, as a directory. The container then
# dies with "exec /usr/local/bin/backup.sh: is a directory: permission denied",
# which names neither the real file nor the real cause, and the stray directory
# then shadows the real script so a later pull cannot fix it either.
#
# Copied into the image instead, a missing script is a build failure that names
# the file. There is nothing left to go wrong at runtime.
#
# postgres:16 as the base is deliberate and load-bearing: pg_dump refuses to
# talk to a server newer than itself, so it must match the postgres service's
# major version. Sharing the base image makes that true by construction rather
# than by someone remembering to bump two places at once -- if you upgrade the
# database, change both, and the build will still be using the same tag.
FROM postgres:16

# rclone moves the copy, age encrypts it. Both are single binaries in Debian,
# so this stays a two-package image rather than a build.
#
# age encrypts to a *public* key, which is what lets this container write
# backups it cannot itself read -- the private half never comes near the box.
RUN apt-get update && apt-get install -y --no-install-recommends \
    rclone \
    age \
    && rm -rf /var/lib/apt/lists/*

COPY backup.sh /usr/local/bin/backup.sh
COPY offsite.sh /usr/local/bin/offsite.sh
COPY verify-offsite.sh /usr/local/bin/verify-offsite.sh
# The drill needs psql/pg_dump/pg_restore, which this image already has by
# virtue of its base -- so it runs in here rather than expecting a Postgres
# client on the Unraid host, which there is no reason to install:
#
#     docker compose run --rm --entrypoint /usr/local/bin/drill.sh backup
COPY drill.sh /usr/local/bin/drill.sh
RUN chmod 0755 \
    /usr/local/bin/backup.sh \
    /usr/local/bin/offsite.sh \
    /usr/local/bin/verify-offsite.sh \
    /usr/local/bin/drill.sh

ENTRYPOINT ["/usr/local/bin/backup.sh"]
