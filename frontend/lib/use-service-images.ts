"use client";

import { useCallback, useEffect, useState } from "react";
import * as api from "./api";

/**
 * The service tier banners the operator has uploaded, as {slug: version}.
 *
 * Starts empty and stays empty if the request fails -- a missing image just
 * means the card renders without one, so a marketing page should never show
 * an error over it. `refresh` lets the admin form re-read the manifest after
 * an upload so the thumbnail updates without a reload.
 */
export function useServiceImages(): {
  images: api.ServiceImageVersions;
  refresh: () => Promise<void>;
} {
  const [images, setImages] = useState<api.ServiceImageVersions>({});

  const refresh = useCallback(async () => {
    try {
      setImages(await api.getServiceImages());
    } catch {
      // Leave whatever we had; the page is still usable without banners.
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return { images, refresh };
}
