"""The maintenance Worker must never gate Stripe's webhook.

The Worker answers before the tunnel, so with the maintenance route attached
every delivery gets its 503; Stripe retries for days, then disables the
endpoint, with nothing in origin logs because nothing reached the origin.
This ties the Worker's bypass list to the route's real path so neither end
can move alone.
"""

import re
from pathlib import Path

from zgrader.api.main import app

WORKER = Path(__file__).resolve().parents[2] / "infra" / "cloudflare" / "maintenance-worker.js"


def _bypass_prefixes() -> list[str]:
    match = re.search(r"const BYPASS_PREFIXES = \[(.*?)\];", WORKER.read_text(encoding="utf-8"), re.S)
    assert match, "BYPASS_PREFIXES not found in maintenance-worker.js"
    return re.findall(r'"([^"]+)"', match.group(1))


def _walk(routes):
    # Mirrors tests/test_rate_limit_coverage.py's _walk: this FastAPI wraps
    # each included router as an _IncludedRouter at the top level of
    # app.routes, with no .path of its own -- the real APIRoute objects only
    # appear inside original_router.routes. Without recursing here, every
    # `getattr(r, "path", "")` on the top level comes back "", nothing ends
    # with "/billing/webhook", and the test fails on a StopIteration that has
    # nothing to do with whether the route is actually bypassed.
    for route in routes:
        original = getattr(route, "original_router", None)
        if original is not None:
            yield from _walk(original.routes)
        else:
            yield route


def test_the_webhook_route_is_bypassed():
    paths = [getattr(r, "path", "") for r in _walk(app.routes)]
    webhook = next(p for p in paths if p.endswith("/billing/webhook"))
    public = "/api" + webhook  # Next.js rewrites /api/:path* to the backend
    assert any(public.startswith(prefix) for prefix in _bypass_prefixes()), (
        f"{public} is not in the maintenance Worker's BYPASS_PREFIXES"
    )
