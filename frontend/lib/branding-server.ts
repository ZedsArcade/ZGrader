import type { Branding } from "./api";

/**
 * Server-side branding lookup, for `generateMetadata` in server components.
 *
 * Why this exists rather than reusing lib/api.ts: `API_BASE` there is "/api",
 * a relative URL that only resolves in the browser, where next.config.ts's
 * rewrite forwards it to the backend. A server-side fetch needs the absolute
 * origin, so this reads BACKEND_URL exactly as next.config.ts does.
 *
 * Do not import this from a client component -- BACKEND_URL is deliberately
 * server-only and must not reach the browser bundle.
 */

/** Mirrors DEFAULT_BRANDING in branding-context.tsx. */
export const FALLBACK_BUSINESS_NAME = "Card Care Center";
export const FALLBACK_CARE_BUSINESS_NAME = "GemCare";

/**
 * How long a fetched business name stays cached.
 *
 * This is also what makes the change work at all. The pages using it are
 * statically generated, and `next build` runs in an isolated Docker stage
 * (frontend/Dockerfile) where the backend container is not running -- so the
 * build-time fetch always fails and falls back. Without a revalidation window
 * the fallback would be baked into the HTML permanently and renaming the
 * business would never show up in the tab title or link previews. Opting the
 * fetch into the data cache with a TTL is what lets the real name appear at
 * runtime while keeping these pages static rather than forcing them dynamic,
 * which next.config.ts deliberately avoids for the marketing pages.
 */
const REVALIDATE_SECONDS = 3600;

async function fetchBranding(): Promise<Partial<Branding> | null> {
  const backendUrl = process.env.BACKEND_URL ?? "http://localhost:8000";
  try {
    const res = await fetch(`${backendUrl}/catalog/branding`, {
      next: { revalidate: REVALIDATE_SECONDS },
    });
    if (!res.ok) return null;
    return (await res.json()) as Partial<Branding>;
  } catch {
    // An unreachable backend must never fail a build or a page render --
    // same reasoning as BrandingProvider swallowing its own fetch error.
    return null;
  }
}

/** The analysis/pre-grading brand, and the legal name used on reports. */
export async function getServerBusinessName(): Promise<string> {
  const branding = await fetchBranding();
  return branding?.business_name?.trim() || FALLBACK_BUSINESS_NAME;
}

/** The card-care / restoration brand, for metadata on the /care routes. */
export async function getServerCareBusinessName(): Promise<string> {
  const branding = await fetchBranding();
  return branding?.care_business_name?.trim() || FALLBACK_CARE_BUSINESS_NAME;
}
