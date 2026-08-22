#!/usr/bin/env bash
#
# A backup and restore rehearsal against throwaway data.
#
# The point is to make a mistake somewhere it costs nothing. Restoring for real
# is the first time most people run pg_restore, under pressure, having never
# seen its output -- this exists so that is the second time.
#
# It builds a scratch database and a directory of fake scans and reports, backs
# them up with the real backup.sh, destroys them, restores, and checks that what
# came back matches what went in. Nothing here touches the live database, the
# live directories, or the live backup destination.
#
#     infra/backup/drill.sh
#
# Requires: a reachable Postgres, and the pg_* client tools. Point it at a
# database you do not care about -- it drops and recreates it.

set -euo pipefail

DRILL_DB="${DRILL_DB:-zgrader_drill}"
PGHOST="${PGHOST:-localhost}"
PGPORT="${PGPORT:-5432}"
PGUSER="${POSTGRES_USER:-zgrader}"
export PGPASSWORD="${POSTGRES_PASSWORD:-zgrader}"

log() { printf '\n=== %s\n' "$*"; }

# Refuse anything that is not obviously scratch. The suite guards itself the
# same way (a database name must end in _test) for the same reason: one typo
# here would drop the real thing.
case "$DRILL_DB" in
  *drill*|*_test) ;;
  *) echo "refusing to run against '${DRILL_DB}' -- name it something containing 'drill'" >&2; exit 1 ;;
esac

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
data="${work}/data"
backups="${work}/backups"
mkdir -p "${data}/reports/SUB-00001" "${data}/scans/SUB-00001" "$backups"

log "building throwaway data"
printf 'pretend front scan\n' > "${data}/scans/SUB-00001/front.jpg"
printf 'pretend annotated image\n' > "${data}/reports/SUB-00001/front_base.jpg"
printf 'pretend report\n' > "${data}/reports/SUB-00001/report.pdf"

psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d postgres -v ON_ERROR_STOP=1 \
  -c "DROP DATABASE IF EXISTS ${DRILL_DB}" -c "CREATE DATABASE ${DRILL_DB}" > /dev/null
psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$DRILL_DB" -v ON_ERROR_STOP=1 > /dev/null <<SQL
CREATE TABLE submissions (id int primary key, code text not null);
INSERT INTO submissions VALUES (1, 'SUB-00001'), (2, 'SUB-00002');
SQL
echo "  2 rows, 3 files"

log "taking a backup with the real script"
BACKUP_DIR="$backups" BACKUP_DATA_DIR="$data" POSTGRES_DB="$DRILL_DB" \
  PGHOST="$PGHOST" POSTGRES_USER="$PGUSER" \
  "$(dirname "${BASH_SOURCE[0]}")/backup.sh" --once

log "destroying the originals"
psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d postgres -v ON_ERROR_STOP=1 \
  -c "DROP DATABASE ${DRILL_DB}" -c "CREATE DATABASE ${DRILL_DB}" > /dev/null
rm -rf "${data:?}/reports" "${data:?}/scans"
echo "  database emptied, files deleted"

log "restoring"
dump="$(find "$backups" -name 'db-*.dump' | sort | tail -1)"
archive="$(find "$backups" -name 'files-*.tar.gz' | sort | tail -1)"
pg_restore -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$DRILL_DB" "$dump"
tar xzf "$archive" -C "$data"

log "checking what came back"
rows="$(psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$DRILL_DB" -tAc 'SELECT count(*) FROM submissions')"
files="$(find "${data}/reports" "${data}/scans" -type f | wc -l | tr -d ' ')"
[ "$rows" = "2" ] || { echo "FAILED: expected 2 rows, got ${rows}" >&2; exit 1; }
[ "$files" = "3" ] || { echo "FAILED: expected 3 files, got ${files}" >&2; exit 1; }

psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d postgres -c "DROP DATABASE ${DRILL_DB}" > /dev/null

printf '\nOK -- %s rows and %s files restored. The procedure works.\n' "$rows" "$files"
printf 'For the offsite half, run infra/backup/verify-offsite.sh with your age key.\n'
