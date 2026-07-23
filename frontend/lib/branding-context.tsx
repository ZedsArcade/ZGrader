"use client";

import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import * as api from "./api";

const DEFAULT_BRANDING: api.Branding = { business_name: "Card Care Center", business_contact: null };

interface BrandingContextValue extends api.Branding {
  refresh: () => Promise<void>;
}

const BrandingContext = createContext<BrandingContextValue>({
  ...DEFAULT_BRANDING,
  refresh: async () => {},
});

export function BrandingProvider({ children }: { children: ReactNode }) {
  const [branding, setBranding] = useState<api.Branding>(DEFAULT_BRANDING);

  const refresh = useCallback(async () => {
    try {
      setBranding(await api.getBranding());
    } catch {
      // Keep whatever we had -- a missing/unreachable backend shouldn't break rendering.
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return <BrandingContext.Provider value={{ ...branding, refresh }}>{children}</BrandingContext.Provider>;
}

export function useBranding(): BrandingContextValue {
  return useContext(BrandingContext);
}
