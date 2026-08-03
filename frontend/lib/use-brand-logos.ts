"use client";

import { useCallback, useEffect, useState } from "react";
import * as api from "./api";

/**
 * The brand header logos the operator has uploaded, as {slug: version}.
 *
 * Mirrors useServiceImages, and fails the same way on purpose: starts empty
 * and stays empty if the request fails, because no logo simply means the
 * header shows the section switch alone. An error state would be worse than
 * the absence it is reporting.
 *
 * `refresh` lets the admin form re-read after an upload so the preview updates
 * without a reload.
 */
export function useBrandLogos(): {
  logos: Record<string, number>;
  refresh: () => Promise<void>;
} {
  const [logos, setLogos] = useState<Record<string, number>>({});

  const refresh = useCallback(async () => {
    try {
      setLogos(await api.getBrandLogos());
    } catch {
      // Leave whatever we had; the header is fine without a logo.
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return { logos, refresh };
}
