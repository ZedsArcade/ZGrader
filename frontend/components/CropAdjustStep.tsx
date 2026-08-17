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
  const [checking, setChecking] = useState(false);
  // Set when the crop check says the card's edges could not be found. Holding
  // the codes rather than a boolean lets the panel below reuse the same
  // wording the results page uses for the same condition.
  const [boundaryWarning, setBoundaryWarning] = useState<string[] | null>(null);

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

  /** Persist the crop and move on. Bypasses the check on purpose -- reached
   *  either because the check passed or because the customer chose to submit
   *  anyway. */
  async function submitCrop() {
    if (!points || !dims) return;
    setConfirming(true);
    try {
      const updated = await api.confirmCrop(token, code, side, toPixels(points));
      onConfirmed(updated);
    } catch (err) {
      // Two refusals here are capacity, not failure, and both are recoverable
      // by waiting -- so they get their own wording. The server's own message
      // is accurate but generic; these say what to do next, which is the
      // difference between "something broke" and "come back in a minute".
      if (err instanceof api.ApiError && err.status === 503) {
        toastError(t.cropAdjust.confirmBusy);
      } else if (err instanceof api.ApiError && err.status === 409) {
        toastError(t.cropAdjust.confirmAlreadyRunning);
      } else {
        toastError(err instanceof api.ApiError ? err.message : t.cropAdjust.confirmFailed);
      }
    } finally {
      setConfirming(false);
    }
  }

  /**
   * Check the crop before committing to it.
   *
   * Confirming advances the submission, so a crop the pipeline cannot use
   * costs the customer a credit and a wait to find out. Across 30 real
   * photographs the fit fell back on a third of uncropped images, and 8 of
   * those 10 failures were recovered by re-cropping alone -- so the common
   * case is one they can fix right here, before paying for it.
   *
   * The warning does not block. Two of the thirty could not be fitted at any
   * crop, and trapping someone behind a check they cannot satisfy is worse
   * than letting them through to an honest "no scores" report.
   */
  async function handleConfirm() {
    if (!points || !dims) return;
    setBoundaryWarning(null);
    setChecking(true);
    try {
      const check = await api.checkCrop(token, code, side, toPixels(points));
      if (!check.boundary_found) {
        setBoundaryWarning(check.limitations);
        return;
      }
    } catch {
      // The check is an optimisation, not a gate. If it is unavailable the
      // customer must still be able to submit -- failing closed here would
      // turn a nice-to-have into an outage of the whole upload flow.
      toastError(t.cropAdjust.checkFailed);
    } finally {
      setChecking(false);
    }
    await submitCrop();
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
            // 44px of transparent hit area around a 24px dot. 24 is the bare
            // WCAG 2.5.8 minimum and was the entire target; this is a corner
            // being dragged to within a millimetre on a phone, which is the
            // hardest precision task in the product. The dot stays its old
            // size because it marks the corner it is claiming.
            className="absolute flex h-11 w-11 -translate-x-1/2 -translate-y-1/2 touch-none items-center justify-center"
            style={{ left: `${x * 100}%`, top: `${y * 100}%`, cursor: "grab" }}
          >
            <span
              aria-hidden="true"
              className="h-6 w-6 rounded-full border-2 border-white shadow-md"
              style={{ backgroundColor: "var(--neon-pink)" }}
            />
          </span>
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
      {boundaryWarning && (
        <div
          role="alert"
          className="flex flex-col gap-3 rounded-lg border-l-4 border border-border p-3"
          style={{ borderLeftColor: "var(--grade-warn)" }}
        >
          <p className="text-sm font-semibold text-foreground">
            {t.cropAdjust.boundaryWarningTitle}
          </p>
          {/* The explanation is the results page's own wording for this
              limitation, not a second phrasing of it. */}
          {boundaryWarning.map((codeName) => {
            const copy =
              t.submissionDetail.limitation[
                codeName as keyof typeof t.submissionDetail.limitation
              ];
            return copy ? (
              <p key={codeName} className="text-sm leading-relaxed text-muted">
                {copy}
              </p>
            ) : null;
          })}
          <p className="text-sm leading-relaxed text-muted">{t.cropAdjust.boundaryWarningHint}</p>
          <div className="flex flex-wrap gap-2">
            <Button variant="primary" size="sm" onPress={() => setBoundaryWarning(null)}>
              {t.cropAdjust.adjustInstead}
            </Button>
            <Button
              variant="outline"
              size="sm"
              onPress={submitCrop}
              isDisabled={confirming}
            >
              {confirming ? t.cropAdjust.confirming : t.cropAdjust.submitAnyway}
            </Button>
          </div>
        </div>
      )}

      <Button
        variant="primary"
        onPress={handleConfirm}
        isDisabled={confirming || snapping || checking || boundaryWarning !== null}
      >
        {checking
          ? t.cropAdjust.checking
          : confirming
            ? t.cropAdjust.confirming
            : t.cropAdjust.confirmButton}
      </Button>
    </div>
  );
}
