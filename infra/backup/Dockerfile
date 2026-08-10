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

COPY backup.sh /usr/local/bin/backup.sh
RUN chmod 0755 /usr/local/bin/backup.sh

ENTRYPOINT ["/usr/local/bin/backup.sh"]
