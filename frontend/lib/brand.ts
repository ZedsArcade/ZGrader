/**
 * Which of the two public brands the visitor is currently in.
 *
 * The rule is: **the path overrides, the preference persists.**
 *
 * /care/* is unambiguously GemCare, so it forces the brand and records the
 * choice. Every other route -- /about, /services, /admin, the dashboard --
 * belongs to both brands, so it follows whatever the visitor last chose.
 *
 * The first version derived the brand from the path alone. That made shared
 * links and server-rendered metadata correct, but it also meant clicking
 * "About" from GemCare silently threw you back to GemLab, which is not what a
 * control presented as a toggle should do. Persisting the choice is what fixes
 * that; the path override is what keeps a shared /care link landing in
 * GemCare for someone who has never been here.
 *
 * The tradeoff kept deliberately: `generateMetadata` runs on the server and
 * cannot see a client-side preference, so a shared page's <title> always names
 * the analysis brand. The visible page follows the toggle, the shareable title
 * follows the URL -- which is the right way round.
 */

export type Brand = "lab" | "care";

export const CARE_PREFIX = "/care";

/** Beside zgrader_locale and zgrader_token. */
export const BRAND_STORAGE_KEY = "zgrader_brand";

export function isBrand(value: unknown): value is Brand {
  return value === "lab" || value === "care";
}

/**
 * The brand this path *forces*, or null when the path belongs to both.
 *
 * Returning null rather than "lab" is the whole point: "this route is
 * GemLab" and "this route doesn't care" are different answers, and conflating
 * them is what made the toggle appear to reset.
 */
export function brandFromPathname(pathname: string): Brand | null {
  return pathname === CARE_PREFIX || pathname.startsWith(`${CARE_PREFIX}/`) ? "care" : null;
}

export function readStoredBrand(): Brand | null {
  try {
    const stored = window.localStorage.getItem(BRAND_STORAGE_KEY);
    return isBrand(stored) ? stored : null;
  } catch {
    // Private-browsing modes can throw on localStorage access; falling back to
    // the default brand is better than breaking every page.
    return null;
  }
}

export function storeBrand(brand: Brand): void {
  try {
    window.localStorage.setItem(BRAND_STORAGE_KEY, brand);
  } catch {
    // Not persisting is survivable -- the session still works, it just won't
    // be remembered.
  }
}

/** Path override, then stored preference, then the default. */
export function resolveBrand(pathname: string, stored: Brand | null): Brand {
  return brandFromPathname(pathname) ?? stored ?? "lab";
}

/**
 * Sets data-brand on <html> before first paint.
 *
 * Injected as an inline <script> in the root layout, the same trick
 * next-themes uses for the light/dark class. Without it a GemCare visitor
 * landing on /about would paint once in the GemLab palette and then repaint,
 * which is a visible flash of the wrong brand.
 *
 * It has to duplicate the resolution order above rather than import it,
 * because it runs before any bundle has loaded -- so keep the two in step.
 * next.config.ts's CSP allows 'unsafe-inline' for script-src, so no nonce is
 * needed.
 */
export const BRAND_INIT_SCRIPT = `(function(){try{
var p=location.pathname;
var care=p==="${CARE_PREFIX}"||p.indexOf("${CARE_PREFIX}/")===0;
var b=care?"care":null;
if(b){try{localStorage.setItem("${BRAND_STORAGE_KEY}",b)}catch(e){}}
else{try{var s=localStorage.getItem("${BRAND_STORAGE_KEY}");if(s==="lab"||s==="care")b=s}catch(e){}}
document.documentElement.setAttribute("data-brand",b||"lab");
}catch(e){}})();`;
