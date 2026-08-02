"use client";

import { useLayoutEffect } from "react";
import { usePathname } from "next/navigation";
import { brandFromPathname } from "@/lib/brand";

/**
 * Keeps data-brand on <html> in step with the route during client-side
 * navigation.
 *
 * The inline BRAND_INIT_SCRIPT in the root layout covers the first paint;
 * this covers every navigation after it, when there is no document reload to
 * re-run that script. useLayoutEffect rather than useEffect so the attribute
 * lands before the browser paints the new route, otherwise moving between
 * GemLab and GemCare flashes the previous palette for a frame.
 *
 * Renders nothing.
 */
export default function BrandSync() {
  const pathname = usePathname();

  useLayoutEffect(() => {
    document.documentElement.setAttribute("data-brand", brandFromPathname(pathname ?? "/"));
  }, [pathname]);

  return null;
}
