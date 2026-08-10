# Backups and restore

The `backup` service in `docker-compose.yml` writes a nightly dump. This file
is about the half that matters more: getting the data back.

**An untested backup is a belief, not a backup.** The restore drill at the
bottom takes about five minutes and is the only thing that turns one into the
other. Do it once now, while the database is small enough that a mistake costs
nothing, and again after any change to the schema or the storage layout.

## What is backed up, and why it is three things

| What | How | Why it matters |
|---|---|---|
| Postgres | `pg_dump -Fc` | Submissions, users, analysis results, report rows |
| `/data/reports` | `tar czf` | Published PDFs, annotated images, **and `public/`** — the operator's brand logos and service-page images |
| `/data/scans` | `tar czf` | Customers' original photographs |

Only the first is in the database. The scans and reports directories are not
represented in Postgres at all — `purge_submission_files()` is the only code
that touches them. **A database-only backup restores rows pointing at files
that no longer exist:** every published report 404s, every annotated image is
missing, and the report rows look perfectly healthy while it happens. That is
why the backup service mounts both directories.

## Two decisions worth not undoing

**`pg_dump`, never a copy of the data directory.** A file-level copy of a
*running* Postgres data directory — which is what a plain appdata backup does —
produces a torn database that sits in the folder looking fine and fails when
you try to restore it. If you also use Unraid's CA Appdata Backup for the rest
of `appdata`, either exclude the Postgres directory or accept that only these
dumps are restorable.

**A full dump, not `--data-only`.** The schema has an index created by raw SQL
in a migration (`ix_users_email_lower`, which enforces case-insensitive email
uniqueness). A data-only restore into a schema built any other way loses it
silently, and the failure surfaces much later as two accounts differing only by
case — the exact bug that index exists to prevent.

## Getting it off the box

The service writes to `BACKUP_HOST_PATH`. **Put that on a different disk from
`POSTGRES_DATA_PATH`,** and get a copy off the machine entirely: a backup that
only exists on the array does not survive the array failing, which is one of
the two things it is for. `rclone` to Backblaze B2 costs pennies at this
volume.

**Encrypt anything that leaves your control.** The dump contains customer email
addresses, password hashes and submission history. Putting that unencrypted in
a third-party bucket is a data-protection question, not just a technical one.
`age -p` or `gpg -c` before upload is enough.

## Taking one right now

Before a migration, a bulk delete, or anything else you would rather be able to
undo:

```bash
docker compose run --rm backup --once
```

Writes one backup to the same destination and exits non-zero if it did not
happen, so it can be chained ahead of whatever you were about to do. This is
the thing that was missing when a destructive change had to be preceded by a
hand-rolled `select *`-to-JSON dump.

## Checking it is working

The service logs one line per run. A glance at `docker logs` should show:

```
2026-08-10T02:00:04Z backup: wrote db-20260810T020004Z.dump (412K) and files-20260810T020004Z.tar.gz (18M)
2026-08-10T02:00:04Z backup: OK -- 14 database backup(s) held
```

Every dump is verified with `pg_restore --list` immediately after it is
written, before it is renamed into place. A dump that wrote but cannot be read
is reported as a failure and left as `.partial` for inspection rather than
being counted as a backup. Rotation only runs after a verified success, so a
run of failures can never delete the last known-good copy.

If you see `FAILED` in those logs, the previous backups are untouched — fix
the cause, don't panic about what is already on disk.

## The restore drill

Run this against a **throwaway database**. Never production, and never
`zgrader_test` — pytest drops every table in that one at session start, so a
test run would destroy whatever you restored into it.

Replace `zgrader-postgres-1` with the actual container name if your stack is
named differently (`docker ps --format '{{.Names}}'`).

**1. Restore into a scratch database**

```bash
docker exec zgrader-postgres-1 createdb -U zgrader restore_check
```

```bash
docker exec -i zgrader-postgres-1 pg_restore -U zgrader -d restore_check < /mnt/user/backups/zgrader/db-20260810T020004Z.dump
```

**2. Check it actually contains something**

```bash
docker exec zgrader-postgres-1 psql -U zgrader -d restore_check -c "SELECT (SELECT count(*) FROM users) AS users, (SELECT count(*) FROM submissions) AS submissions, (SELECT count(*) FROM analysis_results) AS results;"
```

Row counts should match production. A restore that "succeeds" into an empty
database is the failure this step exists to catch.

**3. Check the raw-SQL index survived**

```bash
docker exec zgrader-postgres-1 psql -U zgrader -d restore_check -c "\di ix_users_email_lower"
```

One row. If it is missing you restored data-only, and the case-insensitive
email constraint is gone.

**4. Clean up**

```bash
docker exec zgrader-postgres-1 dropdb -U zgrader restore_check
```

**5. Check the files archive opens**

```bash
tar tzf /mnt/user/backups/zgrader/files-20260810T020004Z.tar.gz | head
```

You should see `reports/` and `scans/` entries.

## Restoring for real

Only after the drill above has passed at least once.

1. **Stop the stack** so nothing writes while you work: `docker compose down`
   (or stop it in Portainer).
2. Bring up only Postgres: `docker compose up -d postgres`.
3. Drop and recreate the database, then `pg_restore` into it as above but with
   `-d zgrader`. Dropping first matters — restoring over a populated database
   produces constraint errors and a half-merged result that is worse than
   either version alone.
4. Unpack the files archive over `REPORTS_DATA_PATH` and `SCANS_HOST_PATH`,
   then fix ownership: `chown -R 99:100` on both. The containers run as
   `99:100`, and a restored tree owned by root means uploads fail with
   `PermissionError` and deletions fail on some submissions and not others.
5. Bring the rest up: `docker compose up -d`.
6. Confirm a published report actually opens in the browser. That is the check
   that proves the database and the files were restored *from the same night* —
   a report row whose PDF is missing is exactly the failure a database-only
   backup produces, and it is worth ruling out explicitly.

## Known gap

The archive is a full copy of reports and scans every run, kept for
`BACKUP_RETENTION_DAYS`. That is fine at current volume and will not be once
there are thousands of submissions — the same bytes get written 14 times over.
The point to change it is when the archive stops being minutes to write, and
the shape of the fix is an rsync-style mirror plus the dated database dumps,
not a bigger disk.
