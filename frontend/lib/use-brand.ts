"use client";

import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { readStoredBrand, resolveBrand, type Brand } from "./brand";

/**
 * The active brand, for components that need to render differently per brand.
 *
 * The stored preference is read in an effect rather than during render, and
 * starts as null. That is deliberate: the server has no access to
 * localStorage, so resolving it during the first render would produce
 * different markup on the server and the client and React would complain. The
 * first render therefore uses the path alone -- which is what the server
 * computed too -- and the stored preference settles in immediately after.
 *
 * The palette itself does not go through this hook. That is set on <html> by
 * the inline script before first paint (see BRAND_INIT_SCRIPT), so there is no
 * flash of the wrong colours even though this hook briefly says "lab".
 */
export function useBrand(): Brand {
  const pathname = usePathname() ?? "/";
  const [stored, setStored] = useState<Brand | null>(null);

  useEffect(() => {
    setStored(readStoredBrand());
  }, [pathname]);

  return resolveBrand(pathname, stored);
}
