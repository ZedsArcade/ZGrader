"use client";

import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import * as api from "./api";
import { useAuth } from "./auth-context";

interface QuotaContextValue {
  quota: api.Quota | null;
  /** Re-read after spending a credit, so the header stops showing a number
   *  the server no longer agrees with. */
  refresh: () => Promise<void>;
}

const QuotaContext = createContext<QuotaContextValue>({
  quota: null,
  refresh: async () => {},
});

/**
 * Holds the signed-in account's remaining checks.
 *
 * Separate from AuthProvider because it changes for a different reason: the
 * user object changes on profile edits and password changes, the quota
 * changes every time a submission is created. Folding them together would
 * mean re-fetching the whole user to update a counter.
 *
 * Null quota means "not known" -- signed out, still loading, or the request
 * failed. Every consumer treats that as "show nothing" rather than "zero
 * left", so a failed fetch never tells someone they are out of credits.
 */
export function QuotaProvider({ children }: { children: ReactNode }) {
  const { token } = useAuth();
  const [quota, setQuota] = useState<api.Quota | null>(null);

  const refresh = useCallback(async () => {
    if (!token) {
      setQuota(null);
      return;
    }
    try {
      setQuota(await api.getQuota(token));
    } catch {
      // Keep whatever we had -- a transient failure shouldn't make the
      // allowance vanish from the header.
    }
  }, [token]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return <QuotaContext.Provider value={{ quota, refresh }}>{children}</QuotaContext.Provider>;
}

export function useQuota(): QuotaContextValue {
  return useContext(QuotaContext);
}
