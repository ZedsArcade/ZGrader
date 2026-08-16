import type { PublicReport } from "./api";

/**
 * Server-side fetch of a shared report.
 *
 * Same reason `branding-server.ts` exists rather than reusing `lib/api.ts`:
 * `API_BASE` there is "/api", a relative URL that only resolves in a browser,
 * where next.config.ts's rewrite forwards it. A server render needs the
 * absolute origin, so this reads BACKEND_URL exactly as that file does.
 *
 * Do not import this from a client component -- BACKEND_URL is server-only and
 * must not reach the browser bundle.
 */

/** Matches `export const revalidate` on the page. The page's own ISR window is
 *  what Cloudflare sees; this keeps the data fetch from being the thing that
 *  makes the route dynamic, which would cost the cacheable Cache-Control header
 *  entirely (see next/dist/docs/01-app/02-guides/cdn-caching.md). */
const REVALIDATE_SECONDS = 60;

/**
 * The report behind a share token, or null.
 *
 * Null covers every failure equally on purpose: a token that never existed, one
 * that was rotated away, and a report that is no longer published all 404 from
 * the API and all become the same `notFound()` here. Distinguishing them on the
 * page would hand somebody probing tokens the one bit the 404 is there to keep.
 */
export async function fetchPublicReport(token: string): Promise<PublicReport | null> {
  const backendUrl = process.env.BACKEND_URL ?? "http://localhost:8000";
  try {
    const res = await fetch(`${backendUrl}/public/reports/${encodeURIComponent(token)}`, {
      next: { revalidate: REVALIDATE_SECONDS },
    });
    if (!res.ok) return null;
    return (await res.json()) as PublicReport;
  } catch {
    // An unreachable backend must not throw out of a server render. The page
    // shows its not-found state, which is wrong-but-harmless for 60 seconds,
    // rather than a framework error page on somebody's shared link.
    return null;
  }
}

/** How a shared card is described in a link preview and a browser tab. */
export function cardTitle(report: PublicReport): string {
  const card = report.card;
  if (!card) return "Pre-grade report";
  const parts = [card.card_name];
  if (card.set_name) parts.push(card.set_name);
  if (card.card_number) parts.push(`#${card.card_number}`);
  return parts.join(" — ");
}
