"use client";

import { useLayoutEffect } from "react";
import { usePathname } from "next/navigation";
import { brandFromPathname, readStoredBrand, resolveBrand, storeBrand } from "@/lib/brand";

/**
 * Keeps data-brand on <html> in step with the route and the stored preference.
 *
 * The inline BRAND_INIT_SCRIPT covers the first paint; this covers every
 * client-side navigation after it, where no document reload re-runs that
 * script. Entering /care/* also persists the choice, so leaving again for a
 * shared page like /about stays in GemCare.
 *
 * useLayoutEffect rather than useEffect so the attribute lands before the
 * browser paints the new route -- otherwise moving between the two brands
 * flashes the previous palette for a frame.
 *
 * Renders nothing.
 */
export default function BrandSync() {
  const pathname = usePathname() ?? "/";

  useLayoutEffect(() => {
    const forced = brandFromPathname(pathname);
    if (forced) storeBrand(forced);
    const brand = resolveBrand(pathname, readStoredBrand());
    document.documentElement.setAttribute("data-brand", brand);
  }, [pathname]);

  return null;
}
