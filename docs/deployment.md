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
| `ZGRADER_SMTP_*` | Account verification and password reset both depend on mail being delivered. With the MailHog defaults, nobody can confirm an address or recover a password. A real relay is required in production. |
| `ZGRADER_ADMIN_EMAIL` / `ZGRADER_ADMIN_PASSWORD` | Optional first-operator bootstrap. Safe to remove after the account exists — re-deploying never overwrites an existing operator's password. |

## Cloudflare Tunnel

The reference setup does not forward any port from the router. `cloudflared`
runs alongside the stack and dials out to Cloudflare; Cloudflare terminates TLS
and forwards to Caddy on port 80 inside the Docker network.

Point the tunnel's public hostname at `http://caddy:80` (put `cloudflared` on
the same compose network), or at `http://<unraid-ip>:8080` if you run it
outside the stack.

**The origin must not also be reachable directly.** Two controls depend on it:

- The backend reads `CF-Connecting-IP` to identify the client for rate
  limiting. Anyone who can reach the origin directly can set that header to
  whatever they like and get a fresh rate-limit bucket per request. The app
  only trusts the header when `ZGRADER_ENV=production`, and the whole scheme
  rests on the tunnel being the only path in.
- HSTS is served with a two-year max-age and `preload`. That is correct behind
  Cloudflare's TLS; it would lock browsers out of a plain-HTTP origin.

So: don't port-forward 8080, and if you expose it on the LAN, keep that to the
LAN.

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

The frontend container has no bind mount and runs as the base image's `node`
user; nothing to configure.

## Upgrading an existing deployment

1. Set `ZGRADER_ENV`, `ZGRADER_SECRET_KEY` and `ZGRADER_SITE_URL` in `.env`
   (see `.env.example`). **The stack will not come up without the first two.**
2. Pull and redeploy. The `migrate` service runs `alembic upgrade head` before
   the backend starts, as it always has.
3. The migration adds the account/consent columns and lowercases existing email
   addresses. If two accounts differ only by case, it **aborts with an
   explanatory error and changes nothing** — that needs a human decision about
   which account is real, not a silent merge.
4. Existing users are marked verified by the migration, so nobody already
   registered is locked out by the new verification requirement.

## Still open

Honest list of what this deployment does *not* have yet:

- **No Postgres backups.** There is no code change that fixes this and it is
  the highest-value operational gap. A nightly `pg_dump` to a separate share is
  enough to start with.
- **The session token lives in `localStorage`,** so an XSS could steal it. The
  CSP and the token-version revocation reduce the exposure; moving to an
  `httpOnly` cookie is the real fix and is a focused piece of work of its own.
  Worth doing before advertising the service widely.
- **No dependency lockfile on the backend,** so each image build resolves the
  newest release of everything, including libraries that parse uploaded bytes.
- **No retention policy** for scans, reports or audit rows. They accumulate
  until deleted by hand.
