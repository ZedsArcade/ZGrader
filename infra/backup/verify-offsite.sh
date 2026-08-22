#!/usr/bin/env bash
#
# Prove the offsite chain end to end, without touching production data.
#
# An untested backup is a belief. This one has more links than the local copy --
# upload, encryption, download, decryption -- and every one of them can fail
# silently in a way only discovered during a restore, which is the worst
# possible moment to discover anything.
#
# What it does: fetch the newest database dump from the remote, decrypt it, and
# ask pg_restore to list its contents. If that works, the whole path works.
#
# **This needs the private key, and that is the point.** Everything else in this
# system runs with only the public half, so the box can write backups it cannot
# read. Verification is therefore a deliberate act by someone who has the key,
# not something the machine does to itself -- run it from your workstation, or
# mount the key just long enough.
#
#     BACKUP_AGE_IDENTITY=/path/to/key.txt infra/backup/verify-offsite.sh
#
# Run it once now, against a backup small enough that a mistake costs nothing.

set -euo pipefail

REMOTE="${BACKUP_OFFSITE_REMOTE:-}"
IDENTITY="${BACKUP_AGE_IDENTITY:-${1:-}}"

log() { printf '%s verify: %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"; }
fail() { printf '%s verify: FAILED -- %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" >&2; }

[ -n "$REMOTE" ] || { fail "BACKUP_OFFSITE_REMOTE is not set"; exit 1; }
[ -n "$IDENTITY" ] || { fail "no age identity given (BACKUP_AGE_IDENTITY, or pass the key file as an argument)"; exit 1; }
[ -f "$IDENTITY" ] || { fail "age identity file not found: $IDENTITY"; exit 1; }

# Newest by name, which is newest by time: the stamp is
# %Y%m%dT%H%M%SZ, so lexical order is chronological order. That is why the
# filenames are shaped that way rather than prettily.
newest="$(rclone lsf "$REMOTE" --include 'db-*.dump.age' | sort | tail -1)"
[ -n "$newest" ] || { fail "no database dumps found at $REMOTE"; exit 1; }
log "newest remote dump: $newest"

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
plain="${work}/restored.dump"

if ! rclone cat "${REMOTE}/${newest}" | age -d -i "$IDENTITY" > "$plain"; then
  fail "could not download and decrypt ${newest} -- check the identity matches BACKUP_AGE_RECIPIENT"
  exit 1
fi

size="$(du -h "$plain" | cut -f1)"
if ! pg_restore --list "$plain" > /dev/null 2>&1; then
  fail "${newest} decrypted to ${size} but pg_restore cannot read it"
  exit 1
fi

count="$(pg_restore --list "$plain" | grep -c '^[0-9]' || true)"
log "OK -- ${newest} decrypted to ${size} and pg_restore lists ${count} objects"
log "the offsite chain works: upload, encryption, download, decryption, readable dump"
