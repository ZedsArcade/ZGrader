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


def _published_bindings(service: dict) -> list[tuple[str, bool]]:
    """(how to describe it, whether it names a host interface) per published port.

    Boundness is decided here, where the entry's structure is still known,
    rather than by inspecting a flattened string afterwards. The two compose
    forms carry the same fact in different shapes, and the first version of
    this file rendered long form down to "127.0.0.1:8080" and then counted
    colons -- which reports a correctly bound long-form entry as an offender,
    because the short form it was modelled on has three fields and that has
    two. A check that fails on compliant config is worse than none: it trains
    whoever hits it to weaken the check.
    """
    out: list[tuple[str, bool]] = []
    for entry in service.get("ports") or []:
        if isinstance(entry, dict):
            # Long form. A host_ip, whatever it is, names an interface.
            host_ip = str(entry.get("host_ip") or "")
            display = f"{host_ip or '<all interfaces>'}:{entry.get('published', '')}"
            out.append((display, bool(host_ip)))
        else:
            # Short form: "[host_ip:]host_port:container_port".
            text = str(entry)
            out.append((text, text.count(":") >= 2 and not text.startswith(":")))
    return out


def test_no_service_publishes_on_all_interfaces():
    compose = yaml.safe_load(COMPOSE_FILE.read_text(encoding="utf-8"))

    offenders = []
    for name, service in (compose.get("services") or {}).items():
        if name in PUBLISHED_ON_ALL_INTERFACES_BY_DESIGN:
            continue
        for display, interface_bound in _published_bindings(service or {}):
            if not interface_bound:
                offenders.append(f"{name}: {display}")

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

    # Matches "Caddyfile" anywhere in the entry, so the variable form
    # (${CADDYFILE_PATH:-./infra/caddy/Caddyfile}) counts. The path is a
    # variable because a relative bind mount resolves against the compose
    # file's directory, which under Portainer holds no checkout -- see the
    # comment on the service.
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


def test_both_compose_port_forms_are_classified_correctly():
    """The parser has to understand both shapes, not just the one in use today.

    docker-compose.yml uses short-form strings throughout, so a bug in the
    long-form branch would sit undetected until somebody switched syntax --
    and would then fail against a *correctly* bound port, which is the failure
    that gets a security check deleted rather than fixed.
    """
    short_bound = _published_bindings({"ports": ["127.0.0.1:8080:80"]})
    short_open = _published_bindings({"ports": ["8080:80"]})
    long_bound = _published_bindings(
        {"ports": [{"target": 80, "published": 8080, "host_ip": "127.0.0.1"}]}
    )
    long_open = _published_bindings({"ports": [{"target": 80, "published": 8080}]})

    assert short_bound[0][1] is True, "loopback short form read as unbound"
    assert short_open[0][1] is False, "all-interfaces short form read as bound"
    assert long_bound[0][1] is True, "loopback long form read as unbound"
    assert long_open[0][1] is False, "all-interfaces long form read as bound"

    # The offender message has to name the interface, or it says nothing useful.
    assert "<all interfaces>" in long_open[0][0]
