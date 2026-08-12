"use client";

import { useRef, type PointerEvent as ReactPointerEvent } from "react";
import type { CenteringWidths } from "@/lib/api";

type Key = keyof CenteringWidths;

const HANDLES: { key: Key; cursor: string }[] = [
  { key: "left_px", cursor: "ew-resize" },
  { key: "right_px", cursor: "ew-resize" },
  { key: "top_px", cursor: "ns-resize" },
  { key: "bottom_px", cursor: "ns-resize" },
];

/**
 * The four centering lines and their drag handles, drawn over the analysed
 * photo.
 *
 * Absolutely positioned to fill its parent, which is the same `relative`
 * container holding the photo and `RegionOverlay` -- so this element's
 * bounding rect *is* the displayed photo's, and pointer positions convert
 * straight into raster pixels against it.
 *
 * Rendered after `RegionOverlay` so the handles sit above its numbered
 * badges; a badge landing on a handle would otherwise swallow the drag.
 */
export default function CenteringLines({
  widths,
  raster,
  enabled,
  handleLabels,
  onDrag,
}: {
  widths: CenteringWidths;
  raster: { w: number; h: number };
  /** False when the operator has set the limit to zero -- lines still draw, so
   *  the customer can see where the border was found, but nothing moves. */
  enabled: boolean;
  handleLabels: Record<Key, string>;
  onDrag: (key: Key, rasterPx: number) => void;
}) {
  const boxRef = useRef<HTMLDivElement>(null);
  const dragging = useRef<Key | null>(null);

  // Fractions of the raster, which is the space the overlay is positioned in.
  const fx = widths.left_px / raster.w;
  const fr = 1 - widths.right_px / raster.w;
  const fy = widths.top_px / raster.h;
  const fb = 1 - widths.bottom_px / raster.h;

  const position: Record<Key, { left: string; top: string }> = {
    left_px: { left: `${fx * 100}%`, top: "50%" },
    right_px: { left: `${fr * 100}%`, top: "50%" },
    top_px: { left: "50%", top: `${fy * 100}%` },
    bottom_px: { left: "50%", top: `${fb * 100}%` },
  };

  function handleMove(event: ReactPointerEvent<HTMLSpanElement>) {
    const key = dragging.current;
    if (!key || !boxRef.current) return;
    const rect = boxRef.current.getBoundingClientRect();
    // The photo is scaled from the raster, so convert the pointer back into
    // raster pixels rather than working in CSS pixels -- otherwise the
    // millimetre limit would mean something different on every screen.
    const px =
      key === "left_px"
        ? ((event.clientX - rect.left) / rect.width) * raster.w
        : key === "right_px"
          ? ((rect.right - event.clientX) / rect.width) * raster.w
          : key === "top_px"
            ? ((event.clientY - rect.top) / rect.height) * raster.h
            : ((rect.bottom - event.clientY) / rect.height) * raster.h;
    onDrag(key, px);
  }

  return (
    <div ref={boxRef} className="absolute inset-0 touch-none select-none">
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
        HANDLES.map((h) => (
          <span
            key={h.key}
            role="slider"
            aria-label={handleLabels[h.key]}
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
            style={{
              left: position[h.key].left,
              top: position[h.key].top,
              backgroundColor: "var(--grade-gem)",
              cursor: h.cursor,
            }}
          />
        ))}
    </div>
  );
}
