#!/usr/bin/env bash
#
# Push a verified local backup somewhere that survives the box.
#
# Called by backup.sh *after* a dump has been written, checked with
# `pg_restore --list` and renamed into place. Uploading only what has already
# been verified is the same rule that governs rotation: nothing acts on a
# backup until it is known to be readable.
#
# **A failure here never fails the local backup.** A dead network, a full
# remote or a mistyped bucket must not turn a good local backup into a failed
# run -- the copy on disk is the one that matters most often, and it is already
# safe by the time this runs.
#
# Destination-agnostic on purpose. rclone treats a local disk, an SMB share, an
# SFTP host and a cloud bucket the same, so *where* the copy goes is a .env
# question rather than a code change. Start with an Unassigned Devices disk and
# add a bucket later without touching this file.
#
# Encryption is to a **public key**, which is the part worth understanding. The
# box holds only the recipient's public half, so it can write backups it cannot
# itself read: someone who takes the machine gets ciphertext. That is strictly
# better than a passphrase, which has to be present to encrypt and therefore
# present to decrypt. Keep the private key off the box -- a password manager,
# or on paper. It is needed only to restore, and losing it means losing every
# offsite backup, so it is worth treating like the only copy it is.

set -euo pipefail

REMOTE="${BACKUP_OFFSITE_REMOTE:-}"
RECIPIENT="${BACKUP_AGE_RECIPIENT:-}"
RETENTION_DAYS="${BACKUP_OFFSITE_RETENTION_DAYS:-30}"

log() { printf '%s offsite: %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"; }
fail() { printf '%s offsite: FAILED -- %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" >&2; }

# Nothing configured is a normal state, not an error. The feature ships before
# the disk exists, so an operator who has not chosen a destination yet gets one
# quiet line rather than a nightly failure to ignore.
if [ -z "$REMOTE" ]; then
  log "no BACKUP_OFFSITE_REMOTE set; keeping backups on this box only"
  exit 0
fi

# Configured but unencrypted is refused rather than defaulted. What leaves here
# is customer card photographs and a dump containing email addresses and
# password hashes. Putting that in someone else's storage in the clear is a
# data-protection decision, and it is not one this script will make silently.
if [ -z "$RECIPIENT" ]; then
  fail "BACKUP_OFFSITE_REMOTE is set but BACKUP_AGE_RECIPIENT is not -- refusing to send customer data unencrypted"
  exit 1
fi

for tool in rclone age; do
  if ! command -v "$tool" > /dev/null 2>&1; then
    fail "$tool is not installed in this image"
    exit 1
  fi
done

uploaded=0
for src in "$@"; do
  [ -f "$src" ] || continue
  name="$(basename "$src").age"
  # Streamed, so the encrypted copy never lands on the disk this is trying to
  # get data *off*. pipefail is what makes a failing `age` visible -- without
  # it the exit status would be rclone's, which would happily report success
  # after writing an empty object.
  if age -r "$RECIPIENT" < "$src" | rclone rcat "${REMOTE}/${name}"; then
    log "sent ${name}"
    uploaded=$((uploaded + 1))
  else
    fail "could not send ${name}; the local copy is untouched"
    exit 1
  fi
done

if [ "$uploaded" -eq 0 ]; then
  log "nothing to send"
  exit 0
fi

# Remote retention is its own number and deliberately longer than the local
# one. Offsite protects against the failures noticed slowly -- ransomware, a
# mistake found weeks later -- so a fortnight there would defeat the point.
if rclone delete --min-age "${RETENTION_DAYS}d" "$REMOTE" 2>/dev/null; then
  log "pruned anything older than ${RETENTION_DAYS}d"
else
  # Non-fatal: the copies are already safely up. A remote that refuses a
  # delete is worth a line, not a failed backup.
  fail "could not prune ${REMOTE} (uploads succeeded)"
fi

log "OK -- ${uploaded} file(s) offsite, retention ${RETENTION_DAYS}d"
