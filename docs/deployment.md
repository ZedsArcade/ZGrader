# Deployment and security notes

This covers running Card Care Center on your own hardware (the reference
deployment is Unraid + Portainer + a Cloudflare Tunnel) and the security
controls that depend on getting the deployment right. `docs/qa_checklist.md`
covers manual functional testing; this file is about the box it runs on.

## Breaking change: the backend now refuses to start on default secrets

`ZGRADER_ENV=production` (the compose default) turns on a startup check. The
backend exits immediately, with the reason printed, if:

- `ZGRADER_SECRET_KEY` is still the value shipped in `backend/zgrader/config.py`,
  or is shorter than 32 characters, or
- the database URL still uses the default `zgrader:zgrader` credentials.

That key signs every session token. Left at the default, anyone who can read
this repository can mint a token for any account, including yours. A crash on
boot is the only failure mode that can't be missed, which is why it is a crash
and not a warning.

Generate the key once and keep it:

```
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

Changing it later invalidates every existing session, which is inconvenient but
not destructive — everyone simply logs in again.

In `development` the same conditions only log a warning, so the bare-`uvicorn`
workflow in the QA checklist and the test suite keep working unchanged.

## Environment variables that matter for security

| Variable | Why it matters |
|---|---|
| `ZGRADER_ENV` | `production` enables the checks above and disables `/api/docs`, `/api/redoc` and `/api/openapi.json`. Left at `development` on a public deployment, the entire admin API surface is published to anonymous visitors. |
| `ZGRADER_SECRET_KEY` | Signs session tokens. See above. |
| `POSTGRES_PASSWORD` | Compose refuses to start without it. |
| `ZGRADER_SITE_URL` | The public origin used to build the links inside verification and password-reset emails. Wrong value here means mail nobody can act on. |
| `ZGRADER_SMTP_*` | **A real relay is required before launch** — see below. |
| `ZGRADER_ADMIN_EMAIL` / `ZGRADER_ADMIN_PASSWORD` | Optional first-operator bootstrap. Safe to remove after the account exists — re-deploying never overwrites an existing operator's password. See below. |
| `ZGRADER_ADMIN_RESET_PASSWORD` | Recovery hatch for a locked-out operator. Off by default. |

## Getting into the admin panel

`ZGRADER_ADMIN_EMAIL` + `ZGRADER_ADMIN_PASSWORD` create an operator on startup, or promote an
existing account of that address to operator. Capitalisation doesn't matter — addresses are
normalised to lowercase everywhere.

The part that catches people out: **if that address already has an account, only the role changes.**
The password stays whatever was set when the account was created, and `ZGRADER_ADMIN_PASSWORD` is
ignored. That's deliberate — otherwise a password you changed in the app would be silently reverted
every time you redeployed, which is a horrible fault to track down.

So if you're locked out:

1. Set `ZGRADER_ADMIN_RESET_PASSWORD=true` alongside the email and password.
2. Redeploy. The backend forces the password onto that account and signs out its existing sessions,
   logging a warning that it did so.
3. Log in, then **remove the flag and redeploy again**. While it's set, the environment file is a
   standing credential for the admin account.

The startup log tells you which path ran — `Seeded operator account for …`, `Promoted … to
operator`, `… already exists; left unchanged`, or `Startup seeding failed` with a traceback. If you
see none of those, the two variables aren't both set.

## Cloudflare Tunnel

The reference setup does not forward any port from the router. `cloudflared`
runs alongside the stack and dials out to Cloudflare; Cloudflare terminates TLS
and forwards to Caddy on port 80 inside the Docker network.

Point the tunnel's public hostname at `http://caddy:80`, with `cloudflared` on
the same compose network — which is how this stack runs it.

Running `cloudflared` *outside* the stack used to be the alternative, pointing
it at `http://<unraid-ip>:8080`. That no longer works and should not be made to
work casually: Caddy publishes on loopback only (see below), so the host's LAN
address does not answer on 8080. Rebinding it to reach that way reopens the
header-spoofing hole described in the next section, so treat it as a change to
the trust model rather than a port edit.

**The origin must not also be reachable directly.** Two controls depend on it:

- The backend reads `CF-Connecting-IP` to identify the client for rate
  limiting. Anyone who can reach the origin directly can set that header to
  whatever they like and get a fresh rate-limit bucket per request. The app
  only trusts the header when `ZGRADER_ENV=production`, and the whole scheme
  rests on the tunnel being the only path in.
- HSTS is served with a two-year max-age and `preload`. That is correct behind
  Cloudflare's TLS; it would lock browsers out of a plain-HTTP origin.

So Caddy publishes on **loopback only** (`127.0.0.1:8080:80`). `cloudflared`
runs in this stack and dials `caddy:80` over the compose network, so nothing
needs the host publish; binding it to loopback makes the rule above true by
construction rather than by everyone remembering it.
`backend/tests/test_compose_port_bindings.py` fails if that reverts.

To reach the origin yourself, forward the port instead of publishing it:

```
ssh -N -L 8080:127.0.0.1:8080 <this-host>
```

**If you ever move `cloudflared` out of the stack**, it can no longer reach
`caddy:80` and will need a routable address again — at which point the trust
placed in `CF-Connecting-IP` has to be re-examined, not just the binding.

## The Caddyfile has to be mounted *and* used

`infra/caddy/Caddyfile` sets slow-client timeouts and a 25MB request-body cap,
both of which matter in front of a single uvicorn worker. For a long time it
did neither: the compose service overrode the command with
`caddy reverse-proxy --from :80 --to frontend:3000`, which ignores
`/etc/caddy/Caddyfile` entirely. The file sat in the repository describing
behaviour nothing exhibited — including the warning not to publish this port.

The image's default entrypoint already runs the Caddyfile, so the service now
mounts it and sets no `command:`. Mounting it while keeping the override would
have changed nothing, which is why the test asserts both halves.

**Where the file has to live depends on how you deploy.** The mount is
`${CADDYFILE_PATH:-./infra/caddy/Caddyfile}`. Running `docker compose up` from a
checkout, the default is right. Deploying through **Portainer** or Unraid's
Compose Manager, it is not: those keep the compose file in their own storage, a
relative bind mount resolves against *that* directory, and there is no checkout
in it. Docker does not call a missing bind source an error — it creates the path
as a directory, and Caddy then fails to start because a directory cannot be
mounted onto a file. The site goes down and the message talks about mounts, not
about a file nobody copied.

So on those setups, copy the file onto the host and point the variable at it:

```
mkdir -p /mnt/user/appdata/zgrader/caddy
cp infra/caddy/Caddyfile /mnt/user/appdata/zgrader/caddy/Caddyfile
```

then set this in the stack's environment:

```
CADDYFILE_PATH=/mnt/user/appdata/zgrader/caddy/Caddyfile
```

**That copy becomes a second source of truth** and will drift from the
repository the first time somebody edits one and not the other. Re-copy it
whenever `infra/caddy/Caddyfile` changes.

**Validate it before deploying a change to it.** A malformed Caddyfile stops
the proxy, and the proxy is the only way in:

```
docker run --rm -v /mnt/user/appdata/zgrader/infra/caddy/Caddyfile:/etc/caddy/Caddyfile:ro   caddy:2-alpine caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
```

## Capacity on a shared box

Two knobs, and they only make sense together.

`ZGRADER_MAX_CONCURRENT_ANALYSES` (default 2) bounds how many analyses run inside
API requests at once. `confirm-crop` runs the OpenCV pipeline in the request, so
without it a burst of submissions turns into a burst of pipelines and starves
everything else on the machine. The worker container runs one more on top, so
the real ceiling is this **+ 1**.

`ZGRADER_ANALYSIS_THREADS` (default 2) bounds how wide each one spreads. Left
alone OpenCV takes a thread per core, so the cap above would limit the number of
analyses while each still used the whole box. Compose passes the same number as
`OMP_NUM_THREADS` and `OPENBLAS_NUM_THREADS`, because NumPy's bundled OpenBLAS
is a separate pool that reads those at import time.

On an 8-core box the defaults give `(2 + 1) × 2 = 6` threads of analysis, leaving
room for Postgres, the frontend and whatever else Unraid is running. Raising
either is an `.env` edit and a restart.

A request that arrives with every slot taken gets **503** with `Retry-After`; a
customer who already has an analysis running gets **409**. Neither waits — a
hang is worse than a clear refusal, and the frontend says so in both languages.

Rate limits are per-IP and in-process (`backend/zgrader/api/ratelimit.py`), which
is correct for one uvicorn worker and **wrong the moment you add `--workers`**:
each worker keeps its own counters and the effective limit multiplies. The same
applies to the capacity cap. If this ever needs more than one worker, both need
replacing with something shared, not tuning.

## Caching shared reports at the edge

Shared reports (`/r/{token}`) are the one part of the site a stranger can reach
in numbers, and the origin is a home server running OpenCV. The application
already does its half:

- The page is an ISR route and is served
  `Cache-Control: s-maxage=60, stale-while-revalidate=...`. Verify with
  `curl -sD - -o /dev/null https://<host>/r/<token> | grep -i cache-control` --
  if it says `private, no-cache, no-store` then the route has become dynamic and
  the caching is gone. That is a regression worth catching, not a tuning detail.
- The images under `/api/public/reports/{token}/...` end in `.png` and carry
  `Cache-Control: public, max-age=3600`.

**Cloudflare will cache the images with no configuration and the HTML with
none.** Its default cache keys off the file extension, so the PNGs are covered
and the page is not. Without a Cache Rule matching `/r/*` with "Cache
Everything", every view of a shared link reaches the origin -- the load this was
designed to avoid. Add the rule; the origin's own `s-maxage` then governs how
long it is held.

Two things the rule must not do, both from
`next/dist/docs/01-app/02-guides/cdn-caching.md`:

- **Do not strip the `rsc` request header**, and keep the `_rsc` search
  parameter in the cache key. They distinguish an HTML response from a React
  Server Components payload; serving one where the other is expected breaks
  client-side navigation.
- **Do not cache `/api/*` beyond the public report paths.** Everything else
  under it is per-account and authenticated.

Revocation interacts with this. Rotating a share token kills the link at the
origin immediately, but a copy already at the edge is served until `s-maxage`
expires -- about a minute, which is the trade the 60s window was chosen for.
Next also emits a very long `stale-while-revalidate`, so in the pathological
case where the origin is unreachable and revalidation keeps failing, an edge
could serve a revoked page for longer than that. If a hard bound matters more
than the caching does, set an explicit `Cache-Control` for `/r/:path*` in
`frontend/next.config.ts` rather than reaching for the global `expireTime`,
which would also shorten the marketing pages' one-hour window.

## Backups

The `backup` service dumps the database and archives the reports and scans
directories nightly. All three, because only the first is in Postgres — a
database-only backup restores rows pointing at files that no longer exist.

Set `BACKUP_HOST_PATH` to somewhere on a **different disk** from
`POSTGRES_DATA_PATH`, and get a copy off the machine: a backup that only exists
on the array does not survive the array failing.

If you also run Unraid's CA Appdata Backup, exclude the Postgres data
directory. A file-level copy of a running Postgres is torn and unrestorable,
and having one sitting there is worse than having none, because you will
believe in it.

**`docs/backup.md` has the restore drill. Run it once before you need it** —
five minutes now, against a database small enough that a mistake costs nothing.

### Worth adding at the Cloudflare edge

Neither is required — the app defends itself without them — but both are free
and both are cheap insurance:

- **A rate-limiting rule on `/api/auth/*`.** The in-process limiter resets when
  the container restarts and only sees one box; the edge rule doesn't.
- **Cloudflare Access in front of `/admin`.** This puts a second,
  independent authentication factor ahead of the admin panel, so a stolen
  operator password isn't sufficient on its own. Configuration, not code.

## Running as a non-root user (Unraid)

Both images now run as a non-root user, so uploaded scans no longer land on the
host owned by root and world-readable.

`/data/scans` is a **bind mount**, so the container's UID has to match the
ownership of the host directory or the container cannot write to it. The
backend image defaults to `99:100` — Unraid's `nobody:users` — which is what
`/mnt/user/appdata/...` is owned by there. On any other host, either chown the
directory to `99:100` or rebuild with your own values:

```
docker build --build-arg APP_UID=1000 --build-arg APP_GID=1000 ./backend
```

Symptom of getting this wrong: the API returns 500 on scan upload and the log
shows `PermissionError` on `/data/scans`.

Changing `APP_UID` after scans exist leaves the older directories owned by the
previous UID. Writing new submissions still works, but *deleting* an old one
fails — removing a file needs write permission on its directory, not the file —
so `purge_submission_files` raises `PermissionError` on some submissions and not
others. Confirm the mismatch with `docker exec <container> id` against the host
directory's owner. Cleaning up already-orphaned directories needs `docker exec
-u 0`, which overrides `USER app` for that one command and changes nothing about
how the service runs.

The frontend container has no bind mount and runs as the base image's `node`
user; nothing to configure.

## The reference deployment has no `docker compose`

Portainer owns the stack and carries its own compose implementation *inside its
own container*. Nothing installs a compose binary on Unraid itself, so every
`docker compose ...` line in these docs works on a development machine and
fails on the box with `unknown command`. The containers are still ordinary
compose containers -- `docker inspect` shows
`com.docker.compose.project=zgrader-app` -- they were simply created by
something you cannot invoke from that shell.

Two consequences, both easier to learn now than at speed.

**The stack directory is Portainer's, and it has no `.git`.** A Repository
stack is exported to `/mnt/user/appdata/portainer/compose/<stack id>/` as a
plain tree plus a `stack.env`, so `git log` there fails and tells you nothing
about which commit is deployed. Check by file instead -- whether a path added
by the change you are looking for exists:

```bash
ls /mnt/user/appdata/portainer/compose/2/backend/zgrader/api/routers/public_reports.py
```

**Anything documented as `docker compose run --rm ... backup` has to be
translated.** The services are already running, so `docker exec` reaches the
same image, environment, network and volumes without needing compose at all:

| Documented | On the box |
|---|---|
| `docker compose run --rm --entrypoint /usr/local/bin/drill.sh backup` | `docker exec -e PGHOST=postgres zgrader-app-backup-1 /usr/local/bin/drill.sh` |
| `docker compose run --rm backup --once` | `docker exec zgrader-app-backup-1 /usr/local/bin/backup.sh --once` |
| `docker compose down` / `up -d` | Stop / start the stack in Portainer |

`PGHOST=postgres` is the addition worth remembering: `drill.sh` defaults it to
`localhost`, which is right from a host that has the client tools and wrong
from inside a container, where Postgres is a service name on the compose
network.

`verify-offsite.sh` is the exception. It needs the age private key *inside* the
container and `docker exec` cannot add a mount, so run it from a workstation
that has `rclone`, `age` and `pg_restore` -- which is where the private key
should be living anyway. If it must happen on the box, a one-off container can
mount the key and borrow the stack's own environment (**untested** -- there is
no offsite remote configured yet):

```bash
docker run --rm \
  --env-file /mnt/user/appdata/portainer/compose/2/stack.env \
  -e BACKUP_AGE_IDENTITY=/key.txt \
  -v /path/to/key.txt:/key.txt:ro \
  zgrader-app-backup /usr/local/bin/verify-offsite.sh
```

## Upgrading an existing deployment

1. Set `ZGRADER_ENV`, `ZGRADER_SECRET_KEY` and `ZGRADER_SITE_URL` in `.env`
   (see `.env.example`). **The stack will not come up without the first two.**
2. Pull and redeploy. The `migrate` service runs `alembic upgrade head` before
   the backend starts, as it always has.

   **A failed build is silent, and looks exactly like a successful one.**
   Compose builds services in parallel and aborts the whole `up` if any of them
   fails, which leaves every previous container running and serving normally.
   The site does not change, so nothing tells you. This is not hypothetical:
   this box served eight days of merged work as "deployed" that way, and the
   only trace was in `docker image ls` timestamps -- the small `backup` image
   had rebuilt, the large `backend` one had not.

   `migrate` hides it rather than catching it. A one-shot service that has
   already exited 0 satisfies `service_completed_successfully`, so a redeploy
   which does not recreate that container never re-runs migrations at all and
   `alembic_version` stays where it was. New code against an old schema is the
   dangerous version of this; that time it was old code against an old schema,
   which is merely wasted.

   The cause was disk. A rebuild holds the old image, the new one and
   BuildKit's cache at once, so it needs headroom well beyond steady state --
   the `backend` image alone is roughly 1.5GB of opencv, scipy, Pillow and
   WeasyPrint, and the build cache had grown to 281 entries. Unraid's default
   20GB `docker.img` is not enough for a stack that builds from source; 60GB
   leaves room. `pip` reports it honestly as `OSError: [Errno 28] No space left
   on device`, but only in the build log Portainer discards when the dialog is
   closed.
3. The migration adds the account/consent columns and lowercases existing email
   addresses. If two accounts differ only by case, it **aborts with an
   explanatory error and changes nothing** — that needs a human decision about
   which account is real, not a silent merge.
4. Existing users are marked verified by the migration, so nobody already
   registered is locked out by the new verification requirement.
5. **Check that it deployed**, rather than assuming it from the absence of an
   error:

   ```bash
   docker ps -a --format '{{.Names}}\t{{.Status}}' | grep zgrader
   ```

   ```bash
   docker exec zgrader-app-postgres-1 sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "select version_num from alembic_version"'
   ```

   Every container should report an age in seconds; `migrate` should show
   `Exited (0)` from moments ago rather than from the previous deploy; and the
   version should be the newest revision in `backend/alembic/versions/`. If
   `migrate`'s timestamp is old while the others are fresh, the build failed --
   read its log before doing anything else.

## Email is not optional

The `ZGRADER_SMTP_*` defaults point at the bundled `mailhog` service, which only runs under the
`dev` compose profile. In a normal production deployment they point at nothing, and **no mail
leaves the server**.

That breaks more than it looks like it does. Creating a submission and uploading a scan both
require a confirmed email address, and the only way to confirm one is the link in the verification
email. So with no relay configured, a customer can register successfully and then discover they
cannot submit a card, with nothing they can do about it. Password reset is equally dead, which is
how an operator ends up locked out with no way back except the database.

Point `ZGRADER_SMTP_*` at a real relay before anyone else uses the site. To check it's working:
register a throwaway account and confirm the verification mail arrives.

## Still open

Honest list of what this deployment does *not* have yet:

- **The session token lives in `localStorage`,** so an XSS could steal it. The
  CSP and the token-version revocation reduce the exposure; moving to an
  `httpOnly` cookie is the real fix and is a focused piece of work of its own.
  Worth doing before advertising the service widely.
- **No retention policy** for scans, reports or audit rows. They accumulate
  until deleted by hand.
