"use client";

import { useEffect, useRef, useState, type PointerEvent as ReactPointerEvent } from "react";
import Button from "@/components/Button";
import Skeleton from "@/components/Skeleton";
import { toastError } from "@/lib/toast";
import { useTranslations } from "@/lib/i18n/context";
import * as api from "@/lib/api";

type NormPoint = [number, number];

export default function CropAdjustStep({
  token,
  code,
  side,
  onConfirmed,
}: {
  token: string;
  code: string;
  side: api.ScanSide;
  onConfirmed: (updated: api.SubmissionDetail) => void;
}) {
  const t = useTranslations();
  const wrapperRef = useRef<HTMLDivElement>(null);
  const dragIndex = useRef<number | null>(null);

  const [photoUrl, setPhotoUrl] = useState<string | null>(null);
  const [dims, setDims] = useState<{ width_px: number; height_px: number } | null>(null);
  const [points, setPoints] = useState<NormPoint[] | null>(null);
  const [confirming, setConfirming] = useState(false);

  useEffect(() => {
    let cancelled = false;
    let objectUrl: string | null = null;

    async function load() {
      try {
        const [blob, suggestion] = await Promise.all([
          api.fetchAuthedImage(token, api.rawScanUrl(code, side)),
          api.suggestCrop(token, code, side),
        ]);
        if (cancelled) return;
        objectUrl = URL.createObjectURL(blob);
        setPhotoUrl(objectUrl);
        setDims({ width_px: suggestion.width_px, height_px: suggestion.height_px });
        setPoints(
          suggestion.points.map(
            ([x, y]) => [x / suggestion.width_px, y / suggestion.height_px] as NormPoint
          )
        );
      } catch (err) {
        toastError(err instanceof api.ApiError ? err.message : t.cropAdjust.loadFailed);
      }
    }

    load();
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, code, side]);

  function clientToNormalized(clientX: number, clientY: number): NormPoint {
    const rect = wrapperRef.current!.getBoundingClientRect();
    const x = Math.min(1, Math.max(0, (clientX - rect.left) / rect.width));
    const y = Math.min(1, Math.max(0, (clientY - rect.top) / rect.height));
    return [x, y];
  }

  function handlePointerDown(index: number, event: ReactPointerEvent<HTMLSpanElement>) {
    event.currentTarget.setPointerCapture(event.pointerId);
    dragIndex.current = index;
  }

  function handlePointerMove(event: ReactPointerEvent<HTMLSpanElement>) {
    if (dragIndex.current === null) return;
    const next = clientToNormalized(event.clientX, event.clientY);
    const index = dragIndex.current;
    setPoints((prev) => {
      if (!prev) return prev;
      const updated = [...prev];
      updated[index] = next;
      return updated;
    });
  }

  function handlePointerUp(event: ReactPointerEvent<HTMLSpanElement>) {
    event.currentTarget.releasePointerCapture(event.pointerId);
    dragIndex.current = null;
  }

  async function handleConfirm() {
    if (!points || !dims) return;
    setConfirming(true);
    try {
      const pixelPoints: api.CropPoint[] = points.map(([x, y]) => [x * dims.width_px, y * dims.height_px]);
      const updated = await api.confirmCrop(token, code, side, pixelPoints);
      onConfirmed(updated);
    } catch (err) {
      toastError(err instanceof api.ApiError ? err.message : t.cropAdjust.confirmFailed);
    } finally {
      setConfirming(false);
    }
  }

  if (!photoUrl || !points) {
    return <Skeleton className="aspect-[3/4] w-full rounded-xl" />;
  }

  // Safe as an SVG polygon under the wrapper's non-uniform (photo aspect
  // ratio vs. viewport) scaling -- unlike the draggable handles themselves,
  // which are plain HTML spans positioned by percentage, not SVG circles,
  // since circles distort into ellipses under anisotropic scaling (see
  // AnnotatedPhoto.tsx, which establishes this same pattern).
  const polygonPoints = points.map(([x, y]) => `${x},${y}`).join(" ");

  return (
    <div className="flex flex-col gap-3 rounded-xl border border-border p-4">
      <p className="text-sm font-semibold text-foreground">{t.cropAdjust.title}</p>
      <p className="text-sm text-muted">{t.cropAdjust.instructions}</p>
      <div ref={wrapperRef} className="relative touch-none select-none">
        <img src={photoUrl} alt="" className="w-full rounded-lg border border-border" draggable={false} />
        <svg
          viewBox="0 0 1 1"
          preserveAspectRatio="none"
          className="pointer-events-none absolute inset-0 h-full w-full"
        >
          <polygon
            points={polygonPoints}
            fill="var(--neon-pink)"
            fillOpacity={0.12}
            stroke="var(--neon-pink)"
            strokeWidth={0.006}
          />
        </svg>
        {points.map(([x, y], i) => (
          <span
            key={i}
            onPointerDown={(e) => handlePointerDown(i, e)}
            onPointerMove={handlePointerMove}
            onPointerUp={handlePointerUp}
            className="absolute h-6 w-6 -translate-x-1/2 -translate-y-1/2 touch-none rounded-full border-2 border-white shadow-md"
            style={{ left: `${x * 100}%`, top: `${y * 100}%`, backgroundColor: "var(--neon-pink)", cursor: "grab" }}
          />
        ))}
      </div>
      <Button variant="primary" onPress={handleConfirm} isDisabled={confirming}>
        {confirming ? t.cropAdjust.confirming : t.cropAdjust.confirmButton}
      </Button>
    </div>
  );
}
