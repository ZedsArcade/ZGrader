"""No production service publishes a port on every interface.

`docs/deployment.md` states the invariant this enforces: **the origin must not
also be reachable directly.** Two controls rest on it, and both fail quietly
rather than loudly:

  - The backend reads `CF-Connecting-IP` to identify a client for rate
    limiting, and trusts it whenever `ZGRADER_ENV=production`. Anything that
    can reach the origin without passing through the tunnel can set that
    header itself and take a fresh rate-limit bucket per request, which
    defeats every limiter in `api/ratelimit.py` at once -- including the
    login throttle and the user-keyed one on `change-password`.
  - HSTS is served with a two-year `max-age` and `preload`. That is right
    behind Cloudflare's TLS and wrong on a plain-HTTP origin.

Neither leaves a trace when it breaks: the limiter still answers 200, and the
site still loads. The only visible difference is that a control everybody
believes is on has stopped working, which is precisely the kind of thing that
survives for months. So the binding is asserted here rather than trusted to a
comment -- `caddy` was published as `"8080:80"` for months with
`infra/caddy/Caddyfile` itself carrying the warning not to.

`cloudflared` reaches Caddy over the compose network, so nothing needs the
host publish. If cloudflared is ever moved *outside* the stack it will need a
reachable address again, and this test is the thing that will object -- read
`docs/deployment.md` before adding an exception for it.
"""

from pathlib import Path

import yaml

COMPOSE_FILE = Path(__file__).resolve().parents[2] / "docker-compose.yml"

#: Services allowed to publish on every interface, with the reason. Adding a
#: name here is a deliberate act: it says this port being reachable from
#: anything that can route to the host is acceptable.
PUBLISHED_ON_ALL_INTERFACES_BY_DESIGN = {
    # Dev-profile only -- `docker compose up` without `--profile dev` never
    # starts it, so it is not part of any deployment this invariant covers.
    "mailhog",
}


def _published_ports(service: dict) -> list[str]:
    """Long- and short-form port entries, as strings."""
    entries = service.get("ports") or []
    out = []
    for entry in entries:
        if isinstance(entry, dict):
            # Long form: a host_ip key is what makes it interface-specific.
            out.append(f"{entry.get('host_ip', '')}:{entry.get('published', '')}")
        else:
            out.append(str(entry))
    return out


def _is_interface_bound(entry: str) -> bool:
    """True when the mapping names a host interface rather than all of them.

    "8080:80" binds 0.0.0.0; "127.0.0.1:8080:80" binds loopback only. The
    difference is one field and no error message.
    """
    return entry.count(":") >= 2 and not entry.startswith(":")


def test_no_service_publishes_on_all_interfaces():
    compose = yaml.safe_load(COMPOSE_FILE.read_text(encoding="utf-8"))

    offenders = []
    for name, service in (compose.get("services") or {}).items():
        if name in PUBLISHED_ON_ALL_INTERFACES_BY_DESIGN:
            continue
        for entry in _published_ports(service or {}):
            if not _is_interface_bound(entry):
                offenders.append(f"{name}: {entry}")

    assert not offenders, (
        "these services publish a port on every interface, so the origin is "
        f"reachable without passing through the Cloudflare Tunnel: {sorted(offenders)}. "
        "Bind them to 127.0.0.1 (see docs/deployment.md), or add the service to "
        "PUBLISHED_ON_ALL_INTERFACES_BY_DESIGN with the reason it is safe."
    )


def test_the_exception_list_names_real_services():
    """Keeps the allowlist honest as docker-compose.yml changes."""
    compose = yaml.safe_load(COMPOSE_FILE.read_text(encoding="utf-8"))
    services = set(compose.get("services") or {})

    stale = PUBLISHED_ON_ALL_INTERFACES_BY_DESIGN - services
    assert not stale, (
        f"PUBLISHED_ON_ALL_INTERFACES_BY_DESIGN names services that no longer exist: {sorted(stale)}"
    )


def test_caddy_loads_the_caddyfile_rather_than_adapter_mode():
    """The Caddyfile has to be both mounted *and* used.

    `caddy reverse-proxy --from :80 --to frontend:3000` ignores
    /etc/caddy/Caddyfile entirely, so for months the file's slow-client
    timeouts and 25MB body cap were inert while the file sat in the repo
    documenting behaviour nothing exhibited -- including the warning about
    not publishing this port, which is what this module exists to enforce.

    Mounting it without dropping the command override changes nothing, which
    is why this asserts both halves.
    """
    compose = yaml.safe_load(COMPOSE_FILE.read_text(encoding="utf-8"))
    caddy = (compose.get("services") or {}).get("caddy") or {}

    mounted = [v for v in (caddy.get("volumes") or []) if "Caddyfile" in str(v)]
    assert mounted, (
        "docker-compose.yml does not mount infra/caddy/Caddyfile into the caddy "
        "service, so its timeouts and request-size cap do nothing."
    )

    command = caddy.get("command")
    assert command is None or "reverse-proxy" not in str(command), (
        "the caddy service overrides its command with `caddy reverse-proxy`, which "
        "ignores the mounted Caddyfile. Remove the override -- the image's default "
        "entrypoint already runs /etc/caddy/Caddyfile."
    )
