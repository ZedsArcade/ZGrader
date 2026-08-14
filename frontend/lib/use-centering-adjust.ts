"use client";

import { useState } from "react";
import { toastError, toastSuccess } from "@/lib/toast";
import { useBranding } from "@/lib/branding-context";
import { useTranslations } from "@/lib/i18n/context";
import * as api from "@/lib/api";

/** The four border widths, in pixels of the rectified card raster. */
type Widths = api.CenteringWidths;

const KEYS = ["left_px", "right_px", "top_px", "bottom_px"] as const;

/**
 * What the centering adjuster needs for a side, or null if it cannot be shown.
 *
 * Three ways it declines, all of them real. A side with no centering result
 * has nothing to draw. An unscored one (`raw_score === null`) has nothing to
 * rescore and the endpoint answers 409 -- offering handles there would invite
 * a click that can only fail. And without `px_per_mm` the operator's
 * millimetre cap cannot be converted into pixels, so the limit the server
 * enforces could not be reflected in what the handles allow.
 */
export function centeringHandles(
  results: api.AnalysisResult[]
): { detected: Widths; pxPerMm: number } | null {
  const result = results.find((r) => r.category === "centering");
  if (!result || result.raw_score === null) return null;
  const m = (result.measurements ?? {}) as Record<string, unknown>;
  const pxPerMm = (m.card_geometry as { px_per_mm?: number } | undefined)?.px_per_mm;
  if (typeof pxPerMm !== "number" || pxPerMm <= 0) return null;
  const widths = KEYS.map((k) => m[k]);
  if (!widths.every((v) => typeof v === "number")) return null;
  const [left_px, right_px, top_px, bottom_px] = widths as number[];
  return { detected: { left_px, right_px, top_px, bottom_px }, pxPerMm };
}

/**
 * The two centering ratios and the worse side, from four border widths.
 *
 * Extracted so the drag overlay and the scorecard cannot disagree about what a
 * set of widths means -- the same reason `centering.ratios_from_widths` exists
 * on the backend. This is the arithmetic half only: pure, so it can be applied
 * to detected widths, adjusted ones, or a mix, wherever a ratio is displayed.
 *
 * The score is still never computed here. That lives in `analysis/scoring.py`,
 * and a second copy in TypeScript is the divergence that has already caught
 * `recompute.py` twice.
 */
export function ratiosFromWidths(widths: Widths): {
  lr: [number, number];
  tb: [number, number];
  worse: number;
} {
  const lr = widths.left_px + widths.right_px;
  const tb = widths.top_px + widths.bottom_px;
  const lrRatio: [number, number] =
    lr > 0 ? [(100 * widths.left_px) / lr, (100 * widths.right_px) / lr] : [50, 50];
  const tbRatio: [number, number] =
    tb > 0 ? [(100 * widths.top_px) / tb, (100 * widths.bottom_px) / tb] : [50, 50];
  return { lr: lrRatio, tb: tbRatio, worse: Math.max(...lrRatio, ...tbRatio) };
}

/**
 * Drag state for the four centering lines, and the one call that rescores.
 *
 * Worth allowing at all because the border detector is the least reliable
 * thing in the pipeline: `border.TRANSITION_DELTA_E` fires on real print
 * texture, and on a full-bleed card back it has been observed reporting a
 * 9.6mm "border" on one side and nothing on the other three. When it puts a
 * line in the wrong place the customer can see that plainly, and before this
 * could do nothing about it.
 *
 * **The ratio updates live; the score does not.** That split is deliberate.
 * The ratio is arithmetic on the handle positions -- `left / (left + right)`
 * -- so computing it here cannot drift from anything. The score is a mapping
 * that lives in `analysis/scoring.py`, and AGENTS.md is explicit that every
 * consumer must route through it; a second copy in TypeScript is exactly the
 * divergence that has already bitten `recompute.py` twice. So the score is
 * recomputed by the server on apply, once.
 *
 * A collector thinks in "55/45" rather than "7.8/10" anyway, so the ratio is
 * also the more useful thing to watch while dragging.
 */
export function useCenteringAdjust({
  token,
  code,
  side,
  detected,
  applied,
  pxPerMm,
  raster,
  onAdjusted,
}: {
  token: string;
  code: string;
  side: api.ScanSide;
  /** Where detection put the lines. Movement is bounded relative to this, and
   *  reset returns here rather than to wherever the client last applied. */
  detected: Widths;
  /** The adjustment already applied, if any. The handles open here so they
   *  show the lines the client last set rather than silently reverting to
   *  detection -- the stored AnalysisResult only ever holds what was
   *  measured, so this is the only record of it. */
  applied?: Widths | null;
  pxPerMm: number;
  /** Natural pixel size of the displayed photo, once it has loaded. */
  raster: { w: number; h: number } | null;
  onAdjusted: (updated: api.SubmissionDetail) => void;
}) {
  const t = useTranslations();
  const { centering_adjust_limit_mm: limitMm } = useBranding();
  const [widths, setWidths] = useState<Widths>(applied ?? detected);
  const [applying, setApplying] = useState(false);

  const limitPx = Math.max(0, limitMm) * pxPerMm;
  const enabled = limitPx > 0 && raster !== null;

  const { lr: lrRatio, tb: tbRatio, worse } = ratiosFromWidths(widths);

  const moved = KEYS.some((k) => Math.abs(widths[k] - detected[k]) > 0.05);
  // Controls also show when an adjustment is already live on the server, so
  // dragging back to the detected lines leaves a way to commit that. Otherwise
  // they would disappear at exactly the moment the client wants to undo,
  // leaving the old nudge scored with nothing on screen to suggest it.
  const showControls = moved || applied != null;

  /** Bounded against where *detection* put the line, not against the previous
   *  drag, so a series of small moves cannot walk past the operator's limit. */
  function clamp(key: keyof Widths, next: number): number {
    if (!raster) return next;
    const span = key === "left_px" || key === "right_px" ? raster.w : raster.h;
    const lo = Math.max(0, detected[key] - limitPx);
    const hi = Math.min(span / 2, detected[key] + limitPx);
    return Math.min(hi, Math.max(lo, next));
  }

  /** Move one line, given a position already converted into raster pixels. */
  function setWidth(key: keyof Widths, rasterPx: number) {
    setWidths((prev) => ({ ...prev, [key]: clamp(key, rasterPx) }));
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

  return {
    widths,
    setWidth,
    reset: () => setWidths(detected),
    apply,
    applying,
    moved,
    showControls,
    enabled,
    limitPx,
    ratios: { lr: lrRatio, tb: tbRatio, worse },
  };
}
