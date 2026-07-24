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
  const [snapping, setSnapping] = useState(false);

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

  function toPixels(pts: NormPoint[]): api.CropPoint[] {
    return pts.map(([x, y]) => [x * dims!.width_px, y * dims!.height_px]);
  }

  // Rotate the 4 handles about their centroid in *pixel* space (rotating in
  // normalized 0..1 space would shear the angle by the image's aspect
  // ratio). Each nudge mutates the points, so it composes with dragging and
  // snapping and needs no backend change -- the existing points -> warp
  // pipeline straightens whatever quad we send.
  function nudgeRotate(degrees: number) {
    if (!dims) return;
    const rad = (degrees * Math.PI) / 180;
    const cos = Math.cos(rad);
    const sin = Math.sin(rad);
    setPoints((prev) => {
      if (!prev) return prev;
      const px = prev.map(([x, y]) => [x * dims.width_px, y * dims.height_px] as [number, number]);
      const cx = px.reduce((s, p) => s + p[0], 0) / px.length;
      const cy = px.reduce((s, p) => s + p[1], 0) / px.length;
      return px.map(([x, y]) => {
        const dx = x - cx;
        const dy = y - cy;
        const rx = cx + dx * cos - dy * sin;
        const ry = cy + dx * sin + dy * cos;
        return [
          Math.min(1, Math.max(0, rx / dims.width_px)),
          Math.min(1, Math.max(0, ry / dims.height_px)),
        ] as NormPoint;
      });
    });
  }

  async function handleSnap() {
    if (!points || !dims) return;
    setSnapping(true);
    try {
      const { points: snapped } = await api.snapCrop(token, code, side, toPixels(points));
      setPoints(snapped.map(([x, y]) => [x / dims.width_px, y / dims.height_px] as NormPoint));
    } catch (err) {
      toastError(err instanceof api.ApiError ? err.message : t.cropAdjust.snapFailed);
    } finally {
      setSnapping(false);
    }
  }

  async function handleConfirm() {
    if (!points || !dims) return;
    setConfirming(true);
    try {
      const updated = await api.confirmCrop(token, code, side, toPixels(points));
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
      <div className="flex flex-wrap items-center gap-2">
        <Button variant="outline" size="sm" onPress={handleSnap} isDisabled={snapping || confirming}>
          {t.cropAdjust.snapButton}
        </Button>
        <Button
          variant="outline"
          size="sm"
          aria-label={t.cropAdjust.rotateLeft}
          onPress={() => nudgeRotate(-1)}
          isDisabled={confirming}
        >
          ⟲
        </Button>
        <Button
          variant="outline"
          size="sm"
          aria-label={t.cropAdjust.rotateRight}
          onPress={() => nudgeRotate(1)}
          isDisabled={confirming}
        >
          ⟳
        </Button>
      </div>
      <Button variant="primary" onPress={handleConfirm} isDisabled={confirming || snapping}>
        {confirming ? t.cropAdjust.confirming : t.cropAdjust.confirmButton}
      </Button>
    </div>
  );
}
