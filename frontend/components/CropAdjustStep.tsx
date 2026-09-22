"use client";

import {
  useEffect,
  useRef,
  useState,
  type CSSProperties,
  type KeyboardEvent as ReactKeyboardEvent,
  type PointerEvent as ReactPointerEvent,
  type ReactNode,
} from "react";
import Button from "@/components/Button";
import Skeleton from "@/components/Skeleton";
import { toastError } from "@/lib/toast";
import { useLocale, useTranslations } from "@/lib/i18n/context";
import * as api from "@/lib/api";

type NormPoint = [number, number];
type CornerKey = "topLeft" | "topRight" | "bottomRight" | "bottomLeft";

/** How far the touch magnifier enlarges the photo, and its diameter. */
const LOUPE_ZOOM = 3;
const LOUPE_PX = 120;
/** Gap between the finger and the magnifier, so the finger never covers it. */
const LOUPE_GAP_PX = 24;
/** Keyboard nudge as a fraction of the photo: fine, and with Shift held. */
const NUDGE = 0.005;
const NUDGE_LARGE = 0.02;

/** Where a drag is, in normalised photo space plus the photo's on-screen size. */
type Loupe = { x: number; y: number; width: number; height: number };

/** Assigns stable labels to a quad of points based on their position relative
 *  to their centroid in sum/difference space. Labels stay with their index
 *  even after drag or nudge, so no duplicate labels appear when one handle
 *  passes another. Returns null for all if four distinct labels cannot be
 *  assigned (collision guard). */
function assignCornerLabels(pts: NormPoint[]): (CornerKey | null)[] {
  if (pts.length !== 4) return [null, null, null, null];

  // Calculate sum and difference for each point; these define corners uniquely
  // for most quads. Sum partitions by diagonal (top-left vs bottom-right);
  // difference partitions by the other diagonal (top-right vs bottom-left).
  const metrics = pts.map(([x, y], i) => ({
    index: i,
    sum: x + y,
    diff: x - y,
  }));

  // Find the index for each corner by its metric extremum
  const topLeftIdx = metrics.reduce((min, m) =>
    m.sum < metrics[min].sum ? m.index : min,
    0,
  );
  const bottomRightIdx = metrics.reduce((max, m) =>
    m.sum > metrics[max].sum ? m.index : max,
    0,
  );
  const topRightIdx = metrics.reduce((max, m) =>
    m.diff > metrics[max].diff ? m.index : max,
    0,
  );
  const bottomLeftIdx = metrics.reduce((min, m) =>
    m.diff < metrics[min].diff ? m.index : min,
    0,
  );

  // Collision guard: if any two rules picked the same index, return null for all
  const indices = [topLeftIdx, bottomRightIdx, topRightIdx, bottomLeftIdx];
  if (new Set(indices).size !== 4) {
    return [null, null, null, null];
  }

  // Assign labels by index
  const result: (CornerKey | null)[] = [null, null, null, null];
  result[topLeftIdx] = "topLeft";
  result[bottomRightIdx] = "bottomRight";
  result[topRightIdx] = "topRight";
  result[bottomLeftIdx] = "bottomLeft";

  return result;
}

export default function CropAdjustStep({
  token,
  code,
  side,
  onConfirmed,
  confirmLabel,
  beforeConfirm,
  onConfirmError,
  children,
}: {
  token: string;
  code: string;
  side: api.ScanSide;
  onConfirmed: (updated: api.SubmissionDetail) => void;
  /** Replaces "Confirm crop" -- the check page says "Analyse card". */
  confirmLabel?: string;
  /** Runs before the crop check. Resolve false to stop; the caller has
   *  already said why. */
  beforeConfirm?: () => Promise<boolean>;
  /** Return true when the caller has shown this refusal itself (the check
   *  page shows a 402 as a panel), so no toast follows. */
  onConfirmError?: (err: api.ApiError) => boolean;
  /** Between the editor and the confirm button: foil, card details. */
  children?: ReactNode;
}) {
  const t = useTranslations();
  const { locale } = useLocale();
  const wrapperRef = useRef<HTMLDivElement>(null);
  const dragIndex = useRef<number | null>(null);

  const [photoUrl, setPhotoUrl] = useState<string | null>(null);
  const [dims, setDims] = useState<{ width_px: number; height_px: number } | null>(null);
  const [points, setPoints] = useState<NormPoint[] | null>(null);
  const [labels, setLabels] = useState<(CornerKey | null)[] | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [snapping, setSnapping] = useState(false);
  const [checking, setChecking] = useState(false);
  const [loupe, setLoupe] = useState<Loupe | null>(null);
  // Set when the crop check says the card's edges could not be found. Holding
  // the codes rather than a boolean lets the panel below reuse the same
  // wording the results page uses for the same condition.
  const [boundaryWarning, setBoundaryWarning] = useState<string[] | null>(null);
  // Which side(s) of the crop disagreed, when the check said so -- named
  // separately from `boundaryWarning` because it renders as one extra
  // sentence on top of the reused limitation copy, not a second explanation.
  const [disagreementSides, setDisagreementSides] = useState<string[]>([]);

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
        const normalizedPoints = suggestion.points.map(
          ([x, y]) => [x / suggestion.width_px, y / suggestion.height_px] as NormPoint
        );
        setPoints(normalizedPoints);
        setLabels(assignCornerLabels(normalizedPoints));
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

  /** Touch only: a mouse pointer is a pixel wide and hides nothing, a finger
   *  hides exactly the corner being placed. */
  function showLoupe(event: ReactPointerEvent<HTMLButtonElement>, point: NormPoint) {
    if (event.pointerType !== "touch" || !wrapperRef.current) return;
    const rect = wrapperRef.current.getBoundingClientRect();
    setLoupe({ x: point[0], y: point[1], width: rect.width, height: rect.height });
  }

  function handlePointerDown(index: number, event: ReactPointerEvent<HTMLButtonElement>) {
    event.currentTarget.setPointerCapture(event.pointerId);
    dragIndex.current = index;
    if (points) showLoupe(event, points[index]);
  }

  function handlePointerMove(event: ReactPointerEvent<HTMLButtonElement>) {
    if (dragIndex.current === null) return;
    const next = clientToNormalized(event.clientX, event.clientY);
    const index = dragIndex.current;
    setPoints((prev) => {
      if (!prev) return prev;
      const updated = [...prev];
      updated[index] = next;
      return updated;
    });
    showLoupe(event, next);
  }

  function handlePointerUp(event: ReactPointerEvent<HTMLButtonElement>) {
    event.currentTarget.releasePointerCapture(event.pointerId);
    dragIndex.current = null;
    setLoupe(null);
  }

  /** The handles were pointer-only; arrow keys make them usable without one. */
  function handleKeyDown(index: number, event: ReactKeyboardEvent<HTMLButtonElement>) {
    const step = event.shiftKey ? NUDGE_LARGE : NUDGE;
    const moves: Record<string, NormPoint> = {
      ArrowLeft: [-step, 0],
      ArrowRight: [step, 0],
      ArrowUp: [0, -step],
      ArrowDown: [0, step],
    };
    const move = moves[event.key];
    if (!move) return;
    event.preventDefault();
    setPoints((prev) => {
      if (!prev) return prev;
      const updated = [...prev];
      const [x, y] = updated[index];
      updated[index] = [
        Math.min(1, Math.max(0, x + move[0])),
        Math.min(1, Math.max(0, y + move[1])),
      ];
      return updated;
    });
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
      const normalizedSnapped = snapped.map(([x, y]) => [x / dims.width_px, y / dims.height_px] as NormPoint);
      setPoints(normalizedSnapped);
      setLabels(assignCornerLabels(normalizedSnapped));
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
      if (err instanceof api.ApiError && onConfirmError?.(err)) {
        // Shown by the caller.
      } else if (err instanceof api.ApiError && err.status === 503) {
        // Two refusals here are capacity, not failure, and both are
        // recoverable by waiting -- so they get their own wording.
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
   * Confirming runs the analysis, so a crop the pipeline cannot use costs
   * the customer a wait to find out. Across 30 real photographs the fit fell
   * back on a third of uncropped images, and 8 of those 10 failures were
   * recovered by re-cropping alone -- so the common case is one they can fix
   * right here.
   *
   * The warning does not block. Two of the thirty could not be fitted at any
   * crop, and trapping someone behind a check they cannot satisfy is worse
   * than letting them through to an honest "no scores" report.
   */
  async function handleConfirm() {
    if (!points || !dims) return;
    setBoundaryWarning(null);
    setDisagreementSides([]);
    if (beforeConfirm && !(await beforeConfirm())) return;
    setChecking(true);
    try {
      const check = await api.checkCrop(token, code, side, toPixels(points));
      if (!check.boundary_found) {
        setBoundaryWarning(check.limitations);
        setDisagreementSides(check.crop_disagreement_sides);
        return;
      }
    } catch {
      // The check is an optimisation, not a gate. If it is unavailable the
      // customer must still be able to submit.
      toastError(t.cropAdjust.checkFailed);
    } finally {
      setChecking(false);
    }
    await submitCrop();
  }

  if (!photoUrl || !points) {
    return <Skeleton className="aspect-[3/4] w-full rounded-xl" />;
  }

  // Safe as an SVG polygon under the wrapper's non-uniform scaling -- unlike
  // the handles, which are HTML positioned by percentage, since circles
  // distort into ellipses under anisotropic scaling (see AnnotatedPhoto.tsx).
  const polygonPoints = points.map(([x, y]) => `${x},${y}`).join(" ");

  let loupeStyle: CSSProperties | null = null;
  if (loupe) {
    const half = LOUPE_PX / 2;
    const px = loupe.x * loupe.width;
    const py = loupe.y * loupe.height;
    // Above the finger, which is what hides the corner; below it only when
    // there is no room above.
    const above = py - LOUPE_PX - LOUPE_GAP_PX;
    loupeStyle = {
      width: LOUPE_PX,
      height: LOUPE_PX,
      left: px - half,
      top: above >= 0 ? above : py + LOUPE_GAP_PX,
      backgroundImage: `url(${photoUrl})`,
      backgroundRepeat: "no-repeat",
      backgroundSize: `${loupe.width * LOUPE_ZOOM}px ${loupe.height * LOUPE_ZOOM}px`,
      backgroundPosition: `${half - px * LOUPE_ZOOM}px ${half - py * LOUPE_ZOOM}px`,
    };
  }

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
          <button
            key={i}
            type="button"
            aria-label={labels?.[i] ? t.cropAdjust.handleLabel[labels[i]!] : `${t.cropAdjust.cornerFallback} ${i + 1}`}
            onPointerDown={(e) => handlePointerDown(i, e)}
            onPointerMove={handlePointerMove}
            onPointerUp={handlePointerUp}
            onKeyDown={(e) => handleKeyDown(i, e)}
            // 44px of transparent hit area around a 24px dot. The dot stays
            // its size because it marks the corner it is claiming.
            className="absolute flex h-11 w-11 -translate-x-1/2 -translate-y-1/2 touch-none items-center justify-center rounded-full focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--neon-pink)]"
            style={{ left: `${x * 100}%`, top: `${y * 100}%`, cursor: "grab" }}
          >
            <span
              aria-hidden="true"
              className="h-6 w-6 rounded-full border-2 border-white shadow-md"
              style={{ backgroundColor: "var(--neon-pink)" }}
            />
          </button>
        ))}
        {loupeStyle && (
          <span
            aria-hidden="true"
            className="pointer-events-none absolute z-10 overflow-hidden rounded-full border-2 border-white shadow-lg"
            style={loupeStyle}
          >
            <span
              className="absolute left-1/2 top-0 h-full w-px -translate-x-1/2"
              style={{ backgroundColor: "var(--neon-pink)" }}
            />
            <span
              className="absolute left-0 top-1/2 h-px w-full -translate-y-1/2"
              style={{ backgroundColor: "var(--neon-pink)" }}
            />
          </span>
        )}
      </div>
      <p className="text-xs text-muted">{t.cropAdjust.keyboardHint}</p>
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
          ⟲ 1°
        </Button>
        <Button
          variant="outline"
          size="sm"
          aria-label={t.cropAdjust.rotateRight}
          onPress={() => nudgeRotate(1)}
          isDisabled={confirming}
        >
          1° ⟳
        </Button>
      </div>
      {boundaryWarning && (
        <div
          role="alert"
          className="flex flex-col gap-3 rounded-lg border-l-4 border border-border p-3"
          style={{ borderLeftColor: "var(--grade-warn)" }}
        >
          <p className="text-sm font-semibold text-foreground">{t.cropAdjust.boundaryWarningTitle}</p>
          {/* The explanation is the results page's own wording for this
              limitation, not a second phrasing of it. */}
          {boundaryWarning.map((codeName) => {
            const copy =
              t.submissionDetail.limitation[codeName as keyof typeof t.submissionDetail.limitation];
            return copy ? (
              <p key={codeName} className="text-sm leading-relaxed text-muted">
                {copy}
              </p>
            ) : null;
          })}
          {/* One extra, minimal sentence naming the side(s) -- the reused
              limitation copy above explains *that* a side disagreed, not
              *which*. */}
          {disagreementSides.length > 0 && (
            <p className="text-sm leading-relaxed text-muted">
              {t.cropAdjust.disagreementSides.replace(
                "{sides}",
                new Intl.ListFormat(locale, { style: "long", type: "conjunction" }).format(
                  disagreementSides.map(
                    (side) => t.cropAdjust.side[side as keyof typeof t.cropAdjust.side] ?? side
                  )
                )
              )}
            </p>
          )}
          <p className="text-sm leading-relaxed text-muted">{t.cropAdjust.boundaryWarningHint}</p>
          <div className="flex flex-wrap gap-2">
            <Button
              variant="primary"
              size="sm"
              onPress={() => {
                setBoundaryWarning(null);
                setDisagreementSides([]);
              }}
            >
              {t.cropAdjust.adjustInstead}
            </Button>
            <Button variant="outline" size="sm" onPress={submitCrop} isDisabled={confirming}>
              {confirming ? t.cropAdjust.confirming : t.cropAdjust.submitAnyway}
            </Button>
          </div>
        </div>
      )}

      {children}

      <Button
        variant="primary"
        onPress={handleConfirm}
        isDisabled={confirming || snapping || checking || boundaryWarning !== null}
      >
        {checking ? t.cropAdjust.checking : confirming ? t.cropAdjust.confirming : confirmLabel ?? t.cropAdjust.confirmButton}
      </Button>
    </div>
  );
}
