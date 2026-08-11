"use client";

import { useEffect, useRef, useState, type PointerEvent as ReactPointerEvent } from "react";
import Button from "@/components/Button";
import Skeleton from "@/components/Skeleton";
import { toastError, toastSuccess } from "@/lib/toast";
import { useBranding } from "@/lib/branding-context";
import { useTranslations } from "@/lib/i18n/context";
import * as api from "@/lib/api";

/** The four border widths, in pixels of the rectified card raster. */
type Widths = api.CenteringWidths;

/**
 * Lets a client move the four centering lines and see the ratio change.
 *
 * Worth allowing because the border detector is the least reliable thing in
 * the pipeline: `border.TRANSITION_DELTA_E` fires on real print texture, and on
 * a full-bleed card back it has been observed reporting a 9.6mm "border" on one
 * side and nothing on the other three. When it puts a line in the wrong place
 * the customer can see that plainly, and until now could do nothing about it.
 *
 * **The ratio updates live; the score does not.** That split is deliberate.
 * The ratio is arithmetic on the handle positions -- `left / (left + right)` --
 * so computing it here cannot drift from anything. The score is a mapping that
 * lives in `analysis/scoring.py`, and AGENTS.md is explicit that every consumer
 * must route through it; a second copy in TypeScript is exactly the divergence
 * that has already bitten `recompute.py` twice. So the score is recomputed by
 * the server on Apply, once.
 *
 * A collector thinks in "55/45" rather than "7.8/10" anyway, so the ratio is
 * also the more useful thing to watch while dragging.
 */
export default function CenteringAdjuster({
  token,
  code,
  side,
  detected,
  applied,
  pxPerMm,
  onAdjusted,
}: {
  token: string;
  code: string;
  side: api.ScanSide;
  /** Where detection put the lines. Movement is bounded relative to this, and
   *  Reset returns here rather than to wherever the client last applied. */
  detected: Widths;
  /** The adjustment already applied, if any. The adjuster opens here so it
   *  shows the lines the client last set rather than silently reverting to
   *  detection -- the stored AnalysisResult only ever holds what was
   *  measured, so this is the only record of it. */
  applied?: Widths | null;
  pxPerMm: number;
  onAdjusted: (updated: api.SubmissionDetail) => void;
}) {
  const t = useTranslations();
  const { centering_adjust_limit_mm: limitMm } = useBranding();
  const wrapperRef = useRef<HTMLDivElement>(null);
  const dragging = useRef<keyof Widths | null>(null);

  const [photoUrl, setPhotoUrl] = useState<string | null>(null);
  const [raster, setRaster] = useState<{ w: number; h: number } | null>(null);
  const [widths, setWidths] = useState<Widths>(applied ?? detected);
  const [applying, setApplying] = useState(false);

  useEffect(() => {
    let cancelled = false;
    let objectUrl: string | null = null;
    api
      .fetchAuthedImage(token, api.sidePhotoUrl(code, side))
      .then((blob) => {
        if (cancelled) return;
        objectUrl = URL.createObjectURL(blob);
        setPhotoUrl(objectUrl);
      })
      .catch(() => toastError(t.centeringAdjust.loadFailed));
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [token, code, side, t.centeringAdjust.loadFailed]);

  const limitPx = Math.max(0, limitMm) * pxPerMm;
  const enabled = limitPx > 0 && raster !== null;

  /** Ratios, live. Pure arithmetic on the handle positions -- see the note on
   *  the component about why the score is not computed here. */
  const lr = widths.left_px + widths.right_px;
  const tb = widths.top_px + widths.bottom_px;
  const lrRatio: [number, number] = lr > 0
    ? [(100 * widths.left_px) / lr, (100 * widths.right_px) / lr]
    : [50, 50];
  const tbRatio: [number, number] = tb > 0
    ? [(100 * widths.top_px) / tb, (100 * widths.bottom_px) / tb]
    : [50, 50];
  const worse = Math.max(...lrRatio, ...tbRatio);
  const moved = (["left_px", "right_px", "top_px", "bottom_px"] as const).some(
    (k) => Math.abs(widths[k] - detected[k]) > 0.05
  );
  // Also shown when an adjustment is already live on the server, so dragging
  // back to the detected lines leaves a way to commit that. Otherwise the
  // controls would disappear at exactly the moment the client wants to undo,
  // leaving the old nudge scored with nothing on screen to suggest it.
  const showControls = moved || applied != null;

  function clamp(key: keyof Widths, next: number): number {
    if (!raster) return next;
    const span = key === "left_px" || key === "right_px" ? raster.w : raster.h;
    // Bounded against where *detection* put the line, not against the previous
    // drag, so a series of small moves cannot walk past the operator's limit.
    const lo = Math.max(0, detected[key] - limitPx);
    const hi = Math.min(span / 2, detected[key] + limitPx);
    return Math.min(hi, Math.max(lo, next));
  }

  function handleMove(event: ReactPointerEvent<HTMLSpanElement>) {
    const key = dragging.current;
    if (!key || !raster || !wrapperRef.current) return;
    const rect = wrapperRef.current.getBoundingClientRect();
    // The displayed element is scaled from the raster, so convert the pointer
    // back into raster pixels rather than working in CSS pixels -- otherwise
    // the millimetre limit would mean something different on every screen.
    const px =
      key === "left_px"
        ? ((event.clientX - rect.left) / rect.width) * raster.w
        : key === "right_px"
          ? ((rect.right - event.clientX) / rect.width) * raster.w
          : key === "top_px"
            ? ((event.clientY - rect.top) / rect.height) * raster.h
            : ((rect.bottom - event.clientY) / rect.height) * raster.h;
    setWidths((prev) => ({ ...prev, [key]: clamp(key, px) }));
  }

  async function apply() {
    setApplying(true);
    try {
      const updated = await api.adjustCentering(token, code, side, {
        left_px: Math.round(widths.left_px * 10) / 10,
        right_px: Math.round(widths.right_px * 10) / 10,
        top_px: Math.round(widths.top_px * 10) / 10,
        bottom_px: Math.round(widths.bottom_px * 10) / 10,
      });
      onAdjusted(updated);
      toastSuccess(t.centeringAdjust.applied);
    } catch (err) {
      // The server enforces the same cap independently, so a rejection here is
      // worth showing rather than swallowing -- it means the two disagree.
      toastError(err instanceof api.ApiError ? err.message : t.centeringAdjust.applyFailed);
    } finally {
      setApplying(false);
    }
  }

  if (!photoUrl) return <Skeleton className="aspect-[3/4] w-full rounded-xl" />;

  // Fractions of the raster, which is what the overlay is positioned in.
  const fx = raster ? widths.left_px / raster.w : 0;
  const fr = raster ? 1 - widths.right_px / raster.w : 1;
  const fy = raster ? widths.top_px / raster.h : 0;
  const fb = raster ? 1 - widths.bottom_px / raster.h : 1;

  const handles: { key: keyof Widths; left: string; top: string; cursor: string }[] = [
    { key: "left_px", left: `${fx * 100}%`, top: "50%", cursor: "ew-resize" },
    { key: "right_px", left: `${fr * 100}%`, top: "50%", cursor: "ew-resize" },
    { key: "top_px", left: "50%", top: `${fy * 100}%`, cursor: "ns-resize" },
    { key: "bottom_px", left: "50%", top: `${fb * 100}%`, cursor: "ns-resize" },
  ];

  return (
    <div className="flex flex-col gap-3 rounded-xl border border-border p-4">
      <p className="text-sm font-semibold text-foreground">{t.centeringAdjust.title}</p>
      <p className="text-sm text-muted">
        {limitPx > 0 ? t.centeringAdjust.instructions : t.centeringAdjust.disabled}
      </p>

      <div ref={wrapperRef} className="relative touch-none select-none">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={photoUrl}
          alt=""
          className="w-full rounded-lg border border-border"
          draggable={false}
          onLoad={(e) =>
            setRaster({ w: e.currentTarget.naturalWidth, h: e.currentTarget.naturalHeight })
          }
        />
        <svg
          viewBox="0 0 1 1"
          preserveAspectRatio="none"
          className="pointer-events-none absolute inset-0 h-full w-full"
        >
          {[
            { x1: fx, y1: 0, x2: fx, y2: 1 },
            { x1: fr, y1: 0, x2: fr, y2: 1 },
            { x1: 0, y1: fy, x2: 1, y2: fy },
            { x1: 0, y1: fb, x2: 1, y2: fb },
          ].map((l, i) => (
            <line
              key={i}
              x1={l.x1}
              y1={l.y1}
              x2={l.x2}
              y2={l.y2}
              stroke="var(--grade-gem)"
              strokeWidth={0.004}
            />
          ))}
        </svg>

        {enabled &&
          handles.map((h) => (
            <span
              key={h.key}
              role="slider"
              aria-label={t.centeringAdjust.handleLabel[h.key]}
              aria-valuenow={Math.round(widths[h.key])}
              tabIndex={0}
              onPointerDown={(e) => {
                e.currentTarget.setPointerCapture(e.pointerId);
                dragging.current = h.key;
              }}
              onPointerMove={handleMove}
              onPointerUp={(e) => {
                e.currentTarget.releasePointerCapture(e.pointerId);
                dragging.current = null;
              }}
              className="absolute h-5 w-5 -translate-x-1/2 -translate-y-1/2 touch-none rounded-full border-2 border-white shadow-md"
              style={{ left: h.left, top: h.top, backgroundColor: "var(--grade-gem)", cursor: h.cursor }}
            />
          ))}
      </div>

      {/* The measurements the request started with -- see the very first ask.
          Shown whether or not anything has been dragged. */}
      <dl className="grid grid-cols-2 gap-x-6 gap-y-1 text-sm">
        <dt className="text-muted">{t.centeringAdjust.leftRight}</dt>
        <dd className="text-right font-medium text-foreground tabular-nums">
          {lrRatio[0].toFixed(1)} / {lrRatio[1].toFixed(1)}
        </dd>
        <dt className="text-muted">{t.centeringAdjust.topBottom}</dt>
        <dd className="text-right font-medium text-foreground tabular-nums">
          {tbRatio[0].toFixed(1)} / {tbRatio[1].toFixed(1)}
        </dd>
        <dt className="text-muted">{t.centeringAdjust.worstSide}</dt>
        <dd className="text-right font-medium text-foreground tabular-nums">{worse.toFixed(1)}%</dd>
      </dl>

      {showControls && (
        <div className="flex flex-wrap gap-2">
          <Button variant="primary" size="sm" isDisabled={applying} onPress={apply}>
            {applying ? t.centeringAdjust.applying : t.centeringAdjust.apply}
          </Button>
          <Button
            variant="outline"
            size="sm"
            isDisabled={applying || !moved}
            onPress={() => setWidths(detected)}
          >
            {t.centeringAdjust.reset}
          </Button>
        </div>
      )}
    </div>
  );
}
