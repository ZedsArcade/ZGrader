"use client";

import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import * as api from "./api";

// Rendered until the backend answers (and kept if it never does). Everything
// optional starts unset so the footer and contact page show nothing rather
// than flashing placeholder links that go nowhere.
const DEFAULT_BRANDING: api.Branding = {
  business_name: "Card Care Center",
  care_business_name: "GemCare",
  business_contact: null,
  contact_email: null,
  contact_location: null,
  contact_response_days: null,
  contact_in_person: false,
  social_instagram: null,
  social_facebook: null,
  social_x: null,
  social_whatsapp: null,
  // Empty until the backend answers. The copy falls back to a generic phrase
  // rather than briefly naming companies that may not be enabled.
  grading_companies: [],
};

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
