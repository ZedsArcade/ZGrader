#!/usr/bin/env bash
#
# Nightly backup of everything a restore needs.
#
# Three things, not one. The database holds submissions, users and analysis
# results; the reports directory holds the published PDFs, the annotated
# images and the operator's uploaded logos; the scans directory holds the
# customer's original photographs. Only the first is in Postgres. A
# database-only backup restores rows pointing at files that no longer exist --
# every published report 404s while its row looks perfectly healthy.
#
# pg_dump rather than a copy of the data directory. Copying a *running*
# Postgres data directory (which is what a plain appdata backup does) produces
# a torn database that sits there looking fine and fails when you try to
# restore it. That is the worst kind of backup: one you believe in.
#
# Restore drill and full procedure: docs/backup.md.

set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/backups}"
# Where reports and scans are mounted. Overridable so the rotation and
# partial-rename logic can be exercised outside a container, against stub
# pg_* binaries -- see tests/test_backup_script.py.
DATA_DIR="${BACKUP_DATA_DIR:-/data}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-14}"
INTERVAL_SECONDS="${BACKUP_INTERVAL_SECONDS:-86400}"
# Sibling script rather than inlined: the local path above is already tested and
# must not regress behind a new feature, and the offsite step needs a different
# failure policy -- it may fail without failing the backup.
OFFSITE_SCRIPT="${BACKUP_OFFSITE_SCRIPT:-$(dirname "${BASH_SOURCE[0]}")/offsite.sh}"
PGHOST="${PGHOST:-postgres}"
PGUSER="${POSTGRES_USER:-zgrader}"
PGDATABASE="${POSTGRES_DB:-zgrader}"
export PGPASSWORD="${POSTGRES_PASSWORD:-}"

log() { printf '%s backup: %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"; }
fail() { printf '%s backup: FAILED -- %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" >&2; }

run_once() {
  local stamp dump_tmp dump_final files_tmp files_final
  stamp="$(date -u +%Y%m%dT%H%M%SZ)"
  dump_final="${BACKUP_DIR}/db-${stamp}.dump"
  files_final="${BACKUP_DIR}/files-${stamp}.tar.gz"
  # Written under a .partial name and renamed only once complete. An
  # interrupted dump must never be left sitting in the directory looking like
  # a good backup -- rotation would eventually delete the real ones around it.
  dump_tmp="${dump_final}.partial"
  files_tmp="${files_final}.partial"

  # -Fc (custom format): compressed, and pg_restore can do selective restores
  # from it. Deliberately a FULL dump rather than --data-only: the schema has
  # an index created by raw SQL in a migration (ix_users_email_lower), and a
  # data-only restore into a schema built any other way loses it silently.
  # That surfaces much later as duplicate accounts differing only by case.
  if ! pg_dump -h "$PGHOST" -U "$PGUSER" -Fc "$PGDATABASE" > "$dump_tmp"; then
    fail "pg_dump did not complete; leaving ${dump_tmp} for inspection"
    return 1
  fi

  # Prove the dump is readable before trusting it. A dump that silently
  # produced nothing useful is the classic backup failure, and it is only ever
  # discovered during a restore, which is the worst possible moment. This
  # costs milliseconds and turns that into a nightly log line.
  if ! pg_restore --list "$dump_tmp" > /dev/null 2>&1; then
    fail "dump wrote but pg_restore cannot read it; leaving ${dump_tmp}"
    return 1
  fi
  mv "$dump_tmp" "$dump_final"

  # Reports and scans. Mounted read-only, so this cannot damage what it is
  # protecting. A missing directory is not an error -- a deployment with no
  # submissions yet has neither, and refusing to back up the database because
  # nobody has uploaded a card would be absurd.
  local targets=()
  [ -d "${DATA_DIR}/reports" ] && targets+=(reports)
  [ -d "${DATA_DIR}/scans" ] && targets+=(scans)

  local produced=("$dump_final")

  if [ "${#targets[@]}" -eq 0 ]; then
    log "wrote $(basename "$dump_final") ($(du -h "$dump_final" | cut -f1)); no reports or scans directories to archive yet"
  else
    if ! tar czf "$files_tmp" -C "$DATA_DIR" "${targets[@]}"; then
      fail "could not archive ${targets[*]} -- the database dump above is still good"
      rm -f "$files_tmp"
      return 1
    fi
    mv "$files_tmp" "$files_final"
    produced+=("$files_final")
    log "wrote $(basename "$dump_final") ($(du -h "$dump_final" | cut -f1)) and $(basename "$files_final") ($(du -h "$files_final" | cut -f1))"
  fi

  # Offsite, if a destination is configured. Deliberately here: after the dump
  # has been proved readable and renamed into place, so only a backup already
  # known to be good is copied anywhere.
  #
  # Its failure is logged and does NOT fail this run. The local copy is already
  # safe by this point, and a dead network must not be reported as a backup
  # problem -- that is how a real failure gets lost among ignorable ones.
  if [ -x "$OFFSITE_SCRIPT" ]; then
    "$OFFSITE_SCRIPT" "${produced[@]}" || fail "offsite copy did not complete; the local backup above is still good"
  fi

  # Rotation runs only after a verified success, so a run of failures can
  # never delete the last known-good backup.
  local removed
  removed="$(find "$BACKUP_DIR" -maxdepth 1 -type f \( -name 'db-*.dump' -o -name 'files-*.tar.gz' \) -mtime "+${RETENTION_DAYS}" -print -delete | wc -l)"
  [ "$removed" -gt 0 ] && log "rotated out ${removed} file(s) older than ${RETENTION_DAYS} days"

  # Loud, because a backup nobody checks is a backup nobody has. This line is
  # what a `docker logs` glance should be able to confirm.
  log "OK -- $(find "$BACKUP_DIR" -maxdepth 1 -name 'db-*.dump' | wc -l) database backup(s) held"
  return 0
}

mkdir -p "$BACKUP_DIR"

until pg_isready -h "$PGHOST" -U "$PGUSER" > /dev/null 2>&1; do
  log "waiting for postgres at ${PGHOST}"
  sleep 5
done

# One backup now, then exit -- for taking a copy before a risky change, and
# what the script's own tests drive:
#
#     docker compose run --rm backup --once
#
# Exits non-zero when the backup did not happen, so it can be chained ahead of
# whatever you were about to do.
if [ "${1:-}" = "--once" ] || [ -n "${BACKUP_RUN_ONCE:-}" ]; then
  log "single run; destination ${BACKUP_DIR}, retention ${RETENTION_DAYS}d"
  if run_once; then
    exit 0
  fi
  fail "this run produced nothing; previous backups are untouched"
  exit 1
fi

log "starting; destination ${BACKUP_DIR}, retention ${RETENTION_DAYS}d, interval ${INTERVAL_SECONDS}s"
while true; do
  # Runs once at startup as well as on the interval, so a redeploy leaves a
  # fresh backup behind rather than a gap -- and a broken configuration is
  # visible in the logs immediately instead of tomorrow.
  run_once || fail "this run produced nothing; previous backups are untouched"
  sleep "$INTERVAL_SECONDS"
done
