/**
 * Which of the two public brands a page belongs to.
 *
 * The brand is derived from the URL rather than stored in localStorage like
 * the locale is. That is deliberate: /care/* has real pages, so the path is
 * already the source of truth. Deriving it means a shared GemCare link opens
 * in GemCare, the back button behaves, and `generateMetadata` on the server
 * can resolve the right brand name -- none of which a client-side toggle can
 * do. The header "toggle" is therefore a link that navigates, not a state
 * flip.
 */

export type Brand = "lab" | "care";

export const CARE_PREFIX = "/care";

export function brandFromPathname(pathname: string): Brand {
  return pathname === CARE_PREFIX || pathname.startsWith(`${CARE_PREFIX}/`) ? "care" : "lab";
}

/**
 * Sets data-brand on <html> before first paint.
 *
 * Injected as an inline <script> in the root layout, the same trick
 * next-themes uses for the light/dark class: without it the page would paint
 * once with the default (lab) palette and then repaint, which on /care is a
 * visible flash of the wrong brand. It is kept in one place here so the
 * selector logic can't drift from brandFromPathname above.
 *
 * next.config.ts's CSP allows 'unsafe-inline' for script-src, so this needs
 * no nonce.
 */
export const BRAND_INIT_SCRIPT = `(function(){try{var p=location.pathname;var c=p==="${CARE_PREFIX}"||p.indexOf("${CARE_PREFIX}/")===0;document.documentElement.setAttribute("data-brand",c?"care":"lab");}catch(e){}})();`;
