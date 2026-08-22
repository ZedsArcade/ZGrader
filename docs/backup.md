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
`POSTGRES_DATA_PATH`** -- a backup that only exists on the array does not
survive the array failing, which is one of the two things it is for.

Beyond that, `offsite.sh` sends an encrypted copy somewhere else after every
verified backup. It is off until you configure it: with
`BACKUP_OFFSITE_REMOTE` empty it logs one line and does nothing, which is a
supported state rather than a broken one.

### Where it goes

Any rclone remote, which is what keeps the destination a `.env` question rather
than a code change. On Unraid the simplest start is a disk outside the array,
mounted with the Unassigned Devices plugin:

```
OFFSITE_HOST_PATH=/mnt/disks/zgrader-backup
RCLONE_CONFIG_OFFSITE_TYPE=local
BACKUP_OFFSITE_REMOTE=offsite:/offsite
```

That survives the array failing and a bad delete. It does **not** survive fire,
theft, or ransomware that reaches a mounted path. For those, either rotate two
disks and keep the spare somewhere else, or add a bucket later -- the script
does not change either way.

### Encryption is to a public key, and that is the point

Generate the pair **off this machine**:

```
age-keygen -o zgrader-backup-key.txt
```

Put the `BACKUP_AGE_RECIPIENT=` public line in `.env`. Put the file itself in a
password manager or on paper, and **not on the server**. The box then holds
only the half that encrypts, so it can write backups it cannot read: someone
who takes the machine gets ciphertext. That is strictly better than a
passphrase, which has to be present to encrypt and is therefore present to
decrypt.

The consequence is worth stating plainly: **lose the private key and every
offsite backup is gone.** It is the only copy.

Without `BACKUP_AGE_RECIPIENT` set, the offsite step refuses to send rather
than uploading customer card photographs and a dump containing email addresses
and password hashes in the clear. That refusal does not fail the local backup.

### Retention

| | kept for | why |
|---|---|---|
| local (`BACKUP_RETENTION_DAYS`) | 14 days | enough to undo a recent mistake |
| offsite (`BACKUP_OFFSITE_RETENTION_DAYS`) | 30 days | the failures offsite protects against are the ones noticed slowly |

**The offsite number is stated in the privacy policy.** Section 5 tells
customers a deleted submission can persist in a backup for up to 30 days, so
changing this setting means changing that page -- otherwise the site is making
a promise the system does not keep, which is the specific thing that section
was corrected to stop doing.

## The service is built, not pulled

`infra/backup/Dockerfile` bakes the script into `postgres:16`. So a change to
`backup.sh` needs the image rebuilt, not just the stack restarted — in
Portainer that is **Pull and redeploy** with *Re-pull image* on, or
`docker compose up -d --build backup` on the command line.

The script used to be bind-mounted instead, which failed whenever the source
was momentarily absent at container start: Docker creates a missing bind source
as a **directory**, the container dies with `is a directory: permission
denied`, and the stray directory then shadows the real script so a later pull
cannot repair it. Baked in, a missing script is a build failure that names the
file.

The base image is pinned to the same major version as the `postgres` service on
purpose. `pg_dump` refuses to talk to a server newer than itself, so upgrading
the database means upgrading both.

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

## Rehearsing it, against data that does not matter

Restoring for real is, for most people, the first time they have ever run
`pg_restore` -- under pressure, having never seen its output. `drill.sh` exists
so that is the second time.

```
docker compose run --rm --entrypoint /usr/local/bin/drill.sh backup
```

It builds a scratch database and a directory of fake scans and reports, backs
them up with the real `backup.sh`, destroys the originals, restores, and checks
that the rows and files came back. It runs inside the backup container because
that image already has the Postgres client tools; there is no reason to install
them on the Unraid host.

It refuses to run against any database whose name does not contain `drill`,
because it drops and recreates whatever it is pointed at. That guard is the
only thing between a rehearsal and an outage, and it is the same shape as the
test suite's refusal to start unless the database ends in `_test`.

### Proving the offsite half

The local drill cannot check encryption, upload or download. That needs the
private key, which by design is not on this machine -- so it is a deliberate
act by someone holding it, not something the server does to itself:

```
BACKUP_AGE_IDENTITY=/path/to/zgrader-backup-key.txt   docker compose run --rm --entrypoint /usr/local/bin/verify-offsite.sh backup
```

That fetches the newest remote dump, decrypts it, and asks `pg_restore` to list
its contents. If it prints OK, the whole chain works: upload, encryption,
download, decryption, readable dump. Every one of those can fail silently and
only be discovered during a restore, which is the worst possible moment to
discover anything.

**Run both once now**, while the database is small enough that a mistake costs
nothing.

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
`BACKUP_RETENTION_DAYS`, so the same bytes get written fourteen times over.

Measured, on one real two-sided submission: **21MB** -- 13MB of customer scans
and 8MB of derived images. At 200 submissions that is about 4GB live and 59GB
across fourteen local copies, which is affordable. It was 173MB per submission
before the derived images were sized properly, where the same arithmetic gave
486GB and the answer was "buy a bigger disk", which was the wrong answer.

So this is no longer urgent, and the trigger to change it is unchanged: when
the archive stops being minutes to write. The shape of the fix is an
rsync-style mirror plus the dated database dumps -- `rclone sync` with
`--backup-dir` for deleted and replaced files -- not a bigger disk.
