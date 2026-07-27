import type { NextConfig } from "next";

// Server-side only (not exposed to the browser) -- the browser always calls
// same-origin /api/*, and Next.js forwards it here. Keeps things same-origin
// in both dev and the docker-compose deployment, with no CORS configuration
// needed on the backend.
const backendUrl = process.env.BACKEND_URL ?? "http://localhost:8000";

const isDev = process.env.NODE_ENV === "development";

// Content-Security-Policy.
//
// script-src carries 'unsafe-inline' because the App Router streams its
// hydration payload through inline <script> tags. Removing it needs a
// per-request nonce, which in this version means a proxy.ts and dynamic
// rendering -- that would drop static generation for every marketing page.
// Worth doing later; noted as a follow-up rather than silently shipped.
//
// So be clear about what this does and doesn't buy: it does NOT stop an
// injected inline script, so it is not on its own a defence for the token in
// localStorage. It does block loading script from any other origin, stop the
// page being framed, forbid plugins, pin <base>, and restrict where forms can
// post -- all of which close off common escalation routes.
//
// style-src needs 'unsafe-inline' too: HeroUI and the theme switcher set
// inline styles, and the landing hero uses an inline gradient.
// img-src needs blob: -- every authenticated image is fetched to a Blob and
// shown via an object URL, because those endpoints need a Bearer token.
const csp = [
  "default-src 'self'",
  `script-src 'self' 'unsafe-inline'${isDev ? " 'unsafe-eval'" : ""}`,
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob:",
  "font-src 'self' data:",
  "connect-src 'self'",
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "frame-ancestors 'none'",
  // Deliberately NO upgrade-insecure-requests.
  //
  // It was here and it broke every plain-HTTP deployment: the browser rewrites
  // every http:// subresource to https://, so on a LAN or homelab install with
  // no TLS listener the stylesheets, scripts and fonts all fail and the site
  // renders as unstyled HTML. It buys nothing in any supported setup either --
  // behind Cloudflare (or a Caddy cert) the document is already served over
  // https, so its relative subresources are https too, with nothing left to
  // upgrade.
  //
  // Worth knowing why this survived testing: localhost is a "potentially
  // trustworthy" origin that the browser never upgrades, so it cannot be
  // reproduced at http://localhost:3000 -- only over a real hostname or IP.
  // docs/qa_checklist.md now says to check the site on its real address.
].join("; ");

const securityHeaders = [
  { key: "Content-Security-Policy", value: csp },
  // Belt and braces with frame-ancestors above, for older browsers.
  { key: "X-Frame-Options", value: "DENY" },
  // Stops a browser second-guessing Content-Type -- relevant because scan
  // downloads fall back to application/octet-stream for unknown suffixes.
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  {
    key: "Permissions-Policy",
    // The card-scanning flow uses a file input with `capture`, which does not
    // need the camera permission -- nothing here needs any of these.
    value: "camera=(), microphone=(), geolocation=(), payment=(), interest-cohort=()",
  },
  // Two years, subdomains included. Only meaningful over HTTPS, which is
  // what Cloudflare terminates in front of this.
  {
    key: "Strict-Transport-Security",
    value: "max-age=63072000; includeSubDomains; preload",
  },
];

const nextConfig: NextConfig = {
  // Leaner production image: `next start` only needs this trimmed output +
  // its own node_modules subset, not the full dev node_modules tree.
  output: "standalone",
  // Don't advertise the framework and version to anyone scanning.
  poweredByHeader: false,
  async headers() {
    return [{ source: "/:path*", headers: securityHeaders }];
  },
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${backendUrl}/:path*`,
      },
    ];
  },
};

export default nextConfig;
