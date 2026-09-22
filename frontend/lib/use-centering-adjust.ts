"use client";

import { useState } from "react";
import { toastError, toastSuccess } from "@/lib/toast";
import { useBranding } from "@/lib/branding-context";
import { useTranslations } from "@/lib/i18n/context";
import * as api from "@/lib/api";

/** The four border widths, in pixels of the rectified card raster. */
type Widths = api.CenteringWidths;
type WidthKey = keyof Widths;

const KEYS = ["left_px", "right_px", "top_px", "bottom_px"] as const;
const SIDE_NAMES: Record<WidthKey, "left" | "right" | "top" | "bottom"> = {
  left_px: "left",
  right_px: "right",
  top_px: "top",
  bottom_px: "bottom",
};
const NO_WIDTHS: Widths = { left_px: 0, right_px: 0, top_px: 0, bottom_px: 0 };

/**
 * "nudge": detection found the border and the customer moves its lines, within
 * the operator's limit either side of where they were found.
 * "place": detection found no printed border, and the customer places the lines
 * by hand, anywhere within the placement bound of the card's edge. The result
 * is scored and labelled as placed by hand.
 */
export type CenteringMode = "nudge" | "place";

export interface CenteringHandles {
  mode: CenteringMode;
  /** nudge: where detection put each line. place: the pipeline's rough
   *  estimate for sides it read, 0 for sides it did not (see `measured`). */
  detected: Widths;
  /** Which entries of `detected` came from the image. All true when nudging. */
  measured: Record<WidthKey, boolean>;
  pxPerMm: number;
}

/**
 * Mirrors `centering.placement_eligible` on the backend, which is the authority
 * and refuses anything this lets through: declined for want of a printed frame,
 * on a card outline that was trusted. `geometry_unverified` is the one
 * disqualifying limitation (`assessment.DISQUALIFYING_LIMITATIONS`).
 */
function placementEligible(m: Record<string, unknown>): boolean {
  const block = m.assessment as api.Assessment | undefined;
  if (!block || block.state === "measured") return false;
  return (
    block.limitations.includes("centering_no_frame") &&
    !block.limitations.includes("geometry_unverified")
  );
}

/**
 * What the centering adjuster needs for a side, or null if it cannot be shown.
 *
 * A scored side is nudged from detection. A side that declined for want of a
 * printed frame is placed by hand. Anything else -- no centering result, or a
 * side whose card outline itself could not be found -- offers nothing, and the
 * endpoint would refuse it. Without `px_per_mm` neither mode can turn the
 * millimetre bounds the server enforces into pixels, so that declines too.
 */
export function centeringHandles(results: api.AnalysisResult[]): CenteringHandles | null {
  const result = results.find((r) => r.category === "centering");
  if (!result) return null;
  const m = (result.measurements ?? {}) as Record<string, unknown>;
  const pxPerMm = (m.card_geometry as { px_per_mm?: number } | undefined)?.px_per_mm;
  if (typeof pxPerMm !== "number" || pxPerMm <= 0) return null;
  const allMeasured = { left_px: true, right_px: true, top_px: true, bottom_px: true };

  if (result.raw_score !== null) {
    const widths = KEYS.map((k) => m[k]);
    if (!widths.every((v) => typeof v === "number")) return null;
    const [left_px, right_px, top_px, bottom_px] = widths as number[];
    return { mode: "nudge", detected: { left_px, right_px, top_px, bottom_px }, measured: allMeasured, pxPerMm };
  }

  if (!placementEligible(m)) return null;
  const estimate = (m.indicative_estimate ?? {}) as Record<string, unknown>;
  const perSide = (estimate.per_side ?? {}) as Record<string, { measured?: boolean } | undefined>;
  const detected = { ...NO_WIDTHS };
  const measured = { left_px: false, right_px: false, top_px: false, bottom_px: false };
  for (const key of KEYS) {
    const value = estimate[key];
    // A width of 0 is the pipeline's refusal, not a reading.
    if (typeof value === "number" && value > 0 && perSide[SIDE_NAMES[key]]?.measured === true) {
      detected[key] = value;
      measured[key] = true;
    }
  }
  return { mode: "place", detected, measured, pxPerMm };
}

/** Where the lines open: detection's for a nudge; for a placement, the rough
 *  estimate where a side was read and `defaultMm` from the edge where not. */
export function startingWidths(handles: CenteringHandles, defaultMm: number): Widths {
  if (handles.mode === "nudge") return handles.detected;
  const start = { ...NO_WIDTHS };
  for (const key of KEYS) {
    start[key] = handles.measured[key] ? handles.detected[key] : defaultMm * handles.pxPerMm;
  }
  return start;
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
 * Drag state for the four centering lines, and the calls that rescore.
 *
 * **The ratio updates live; the score does not.** The ratio is arithmetic on
 * the handle positions, so computing it here cannot drift from anything. The
 * score is a mapping that lives in `analysis/scoring.py`, and every consumer
 * must route through it, so the server computes it on apply, once.
 */
export function useCenteringAdjust({
  token,
  code,
  side,
  handles,
  applied,
  raster,
  onAdjusted,
}: {
  token: string;
  code: string;
  side: api.ScanSide;
  /** From `centeringHandles`; null when this side offers no adjustment. */
  handles: CenteringHandles | null;
  /** The adjustment or placement already applied, if any. The handles open
   *  there rather than silently reverting to where they started. */
  applied?: Widths | null;
  /** Natural pixel size of the displayed photo, once it has loaded. */
  raster: { w: number; h: number } | null;
  onAdjusted: (updated: api.SubmissionDetail) => void;
}) {
  const t = useTranslations();
  const {
    centering_adjust_limit_mm: limitMm,
    centering_placement_max_mm: placeMaxMm,
    centering_placement_default_mm: placeDefaultMm,
  } = useBranding();
  const mode: CenteringMode = handles?.mode ?? "nudge";
  const pxPerMm = handles?.pxPerMm ?? 0;
  const detected = handles?.detected ?? NO_WIDTHS;
  const limitPx = Math.max(0, limitMm) * pxPerMm;
  const placeMaxPx = Math.max(0, placeMaxMm) * pxPerMm;
  const rawStart = handles ? startingWidths(handles, placeDefaultMm) : NO_WIDTHS;
  // A side's indicative_estimate can read past the placement bound --
  // border.MAX_SEARCH_MM is wider than CENTERING_PLACEMENT_MAX_MM -- so an
  // untouched starting line must be clamped here, or Apply refuses a line
  // the customer never touched.
  const start: Widths =
    mode === "place" && placeMaxPx > 0
      ? {
          left_px: Math.min(rawStart.left_px, placeMaxPx),
          right_px: Math.min(rawStart.right_px, placeMaxPx),
          top_px: Math.min(rawStart.top_px, placeMaxPx),
          bottom_px: Math.min(rawStart.bottom_px, placeMaxPx),
        }
      : rawStart;

  const [widths, setWidths] = useState<Widths>(applied ?? start);
  const [applying, setApplying] = useState(false);
  const [clearing, setClearing] = useState(false);

  // The operator's limit is the kill switch for both modes.
  const enabled = limitMm > 0 && pxPerMm > 0 && raster !== null;

  const { lr: lrRatio, tb: tbRatio, worse } = ratiosFromWidths(widths);

  const moved = KEYS.some((k) => Math.abs(widths[k] - start[k]) > 0.05);
  // Controls also show when something is already live on the server, so moving
  // back to the start leaves a way to commit or clear that.
  const showControls = moved || applied != null;

  /** Nudges are bounded against where *detection* put the line, not the last
   *  drag, so small moves cannot walk past the limit. A placement has no
   *  detected line, so it is bounded against the card's edge instead. */
  function boundsPx(key: WidthKey): [number, number] {
    const span = !raster ? Infinity : key === "left_px" || key === "right_px" ? raster.w : raster.h;
    if (mode === "place") return [0, Math.min(span / 2, placeMaxPx)];
    return [Math.max(0, detected[key] - limitPx), Math.min(span / 2, detected[key] + limitPx)];
  }

  function clamp(key: WidthKey, next: number): number {
    if (!raster) return next;
    const [lo, hi] = boundsPx(key);
    return Math.min(hi, Math.max(lo, next));
  }

  /** The same bounds in millimetres, for the handles' aria-valuemin/max. */
  function boundsMm(key: WidthKey): [number, number] {
    const [lo, hi] = boundsPx(key);
    const mm = (px: number) =>
      pxPerMm > 0 && Number.isFinite(px) ? Math.round((px / pxPerMm) * 10) / 10 : 0;
    return [mm(lo), mm(hi)];
  }

  /** Move one line, given a position already converted into raster pixels. */
  function setWidth(key: WidthKey, rasterPx: number) {
    setWidths((prev) => ({ ...prev, [key]: clamp(key, rasterPx) }));
  }

  /** Move one line by a signed number of millimetres of border width. */
  function nudgeBy(key: WidthKey, mm: number) {
    setWidths((prev) => ({ ...prev, [key]: clamp(key, prev[key] + mm * pxPerMm) }));
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
      toastSuccess(mode === "place" ? t.centeringAdjust.placeApplied : t.centeringAdjust.applied);
    } catch (err) {
      // The server enforces the same bounds independently, so a rejection is
      // worth showing rather than swallowing -- it means the two disagree.
      toastError(err instanceof api.ApiError ? err.message : t.centeringAdjust.applyFailed);
    } finally {
      setApplying(false);
    }
  }

  async function clear() {
    setClearing(true);
    try {
      const updated = await api.clearCentering(token, code, side);
      setWidths(start);
      onAdjusted(updated);
      toastSuccess(t.centeringAdjust.cleared);
    } catch (err) {
      toastError(err instanceof api.ApiError ? err.message : t.centeringAdjust.clearFailed);
    } finally {
      setClearing(false);
    }
  }

  return {
    mode,
    widths,
    setWidth,
    nudgeBy,
    reset: () => setWidths(start),
    apply,
    applying,
    clear,
    clearing,
    moved,
    showControls,
    enabled,
    pxPerMm,
    boundsMm,
    ratios: { lr: lrRatio, tb: tbRatio, worse },
  };
}
