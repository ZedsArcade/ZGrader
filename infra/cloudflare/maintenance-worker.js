/**
 * Maintenance page for gemlab.app, served at the Cloudflare edge.
 *
 * This has to be a Worker rather than anything in the Docker stack, and that
 * is the whole point: a maintenance page served *by* the origin cannot appear
 * when the origin is the thing that is down. With cloudflared stopped,
 * Cloudflare has nothing to reach and returns error 1033 -- an unbranded
 * Cloudflare error page with no way to explain what is happening. A Worker
 * runs before the request is routed to the tunnel, so it answers whether or
 * not the stack is running.
 *
 * Deploy: Cloudflare dashboard -> Workers & Pages -> Create -> "Start with
 * Hello World!" (NOT "Upload your static files", which makes a Pages project
 * and cannot run this), then paste this in and Deploy.
 *
 * The switch is the ROUTE, not the Worker. A deployed Worker with no route
 * does nothing; adding the route turns maintenance on, removing it turns it
 * off. Leave the Worker deployed permanently and toggle the route.
 *
 * The route pattern has one trap worth knowing:
 *
 *     gemlab.app/*     matches the apex          <- what you want
 *     *.gemlab.app/*   matches SUBDOMAINS ONLY   <- silently does nothing
 *
 * A domain is not a subdomain of itself, so the wildcard form never matches
 * the apex and the site stays up with no error anywhere to explain why. Add
 * `www.gemlab.app/*` as a second route if www is in use.
 *
 * Returns 503, not 200. That distinction matters more than it looks: a 200
 * tells search engines this page *is* the site, and they will index the
 * maintenance notice in place of the real content. 503 with Retry-After says
 * "temporarily unavailable, come back later", which crawlers understand and
 * which leaves existing rankings alone.
 */

// Roughly how long you expect to be down. Advisory only -- crawlers treat it
// as a hint, not a promise, so an optimistic value costs nothing.
const RETRY_AFTER_SECONDS = 3600;

// Requests allowed through even while maintenance is on. Health checks and
// ACME challenges are the two that break in confusing ways if blocked.
const BYPASS_PREFIXES = ["/.well-known/"];

const PAGE = `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>Back shortly &mdash; GemLab</title>
<style>
  /* Same synthwave tokens as the app's dark theme, so this reads as the
     same site rather than a generic holding page. Light mode mirrors
     frontend/app/tokens.css. */
  :root {
    --bg: #0d0221; --surface: #160b2e; --border: #2d1b52;
    --text: #f5f0ff; --dim: #a89ec9; --accent: #ff2e97; --glow: #ff2e9740;
  }
  @media (prefers-color-scheme: light) {
    :root {
      --bg: #ebe6f3; --surface: #faf8fd; --border: #cec2e1;
      --text: #241736; --dim: #615579; --accent: #c40064; --glow: #c4006433;
    }
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; min-height: 100vh; display: grid; place-items: center;
    padding: 24px; background: var(--bg); color: var(--text);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    line-height: 1.6;
  }
  main {
    max-width: 34rem; width: 100%; padding: 40px 32px;
    background:
      radial-gradient(ellipse at top left, var(--glow), transparent 60%),
      var(--surface);
    border: 1px solid var(--border); border-radius: 12px;
    box-shadow: 0 8px 30px rgba(0,0,0,.25);
  }
  h1 { margin: 20px 0 8px; font-size: 1.75rem; letter-spacing: -0.02em; }
  p { margin: 0 0 12px; color: var(--dim); }
  .note {
    margin-top: 24px; padding-top: 16px; border-top: 1px solid var(--border);
    font-size: .875rem;
  }
  a { color: var(--accent); }
</style>
</head>
<body>
  <main>
    <svg width="40" height="40" viewBox="0 0 40 40" fill="none" aria-hidden="true" style="color: var(--accent)">
      <rect x="8" y="4" width="24" height="32" rx="3" stroke="currentColor" stroke-width="1.5"/>
      <path d="M8 12h24M8 28h24" stroke="currentColor" stroke-width="1" opacity=".55"/>
      <circle cx="20" cy="20" r="4.5" stroke="currentColor" stroke-width="1.5"/>
    </svg>
    <h1>Back shortly</h1>
    <p>GemLab is down for a short spell of maintenance. Nothing is lost &mdash;
       submissions, reports and accounts are all untouched.</p>
    <p>Try again in a little while.</p>
    <p class="note">If you were part-way through something and it looks wrong
       when we're back, email
       <a href="mailto:hello@gemlab.app">hello@gemlab.app</a> and we'll sort it out.</p>
  </main>
</body>
</html>`;

export default {
  async fetch(request) {
    const url = new URL(request.url);

    if (BYPASS_PREFIXES.some((prefix) => url.pathname.startsWith(prefix))) {
      return fetch(request);
    }

    return new Response(PAGE, {
      status: 503,
      headers: {
        "content-type": "text/html; charset=utf-8",
        "retry-after": String(RETRY_AFTER_SECONDS),
        // Never let a CDN or browser hold on to the maintenance page -- it
        // would outlive the maintenance and keep serving after the site is
        // back, which is a far more annoying outage than the original one.
        "cache-control": "no-store, must-revalidate",
      },
    });
  },
};
