"use client";

import {
  useEffect,
  useRef,
  useState,
  type KeyboardEvent as ReactKeyboardEvent,
  type PointerEvent as ReactPointerEvent,
} from "react";
import type { CenteringWidths } from "@/lib/api";

export type LineKey = keyof CenteringWidths;
export type Direction = "up" | "down" | "left" | "right";

const HANDLES: { key: LineKey; cursor: string }[] = [
  { key: "left_px", cursor: "ew-resize" },
  { key: "right_px", cursor: "ew-resize" },
  { key: "top_px", cursor: "ns-resize" },
  { key: "bottom_px", cursor: "ns-resize" },
];

const ARROW_KEYS: Record<string, Direction> = {
  ArrowUp: "up",
  ArrowDown: "down",
  ArrowLeft: "left",
  ArrowRight: "right",
};

/** Loupe diameter, and its gap from the pointer, in CSS pixels. Offset so a
 *  finger never covers the line it is placing. */
const LOUPE_PX = 96;
const LOUPE_GAP_PX = 28;
/** The base photo is at most 1600px on its long side
 *  (`artifacts.MAX_DERIVED_PX`), so past about twice its natural resolution a
 *  loupe only magnifies blur. */
const MAX_LOUPE_ZOOM = 4;

/**
 * Millimetres of border width to add for an arrow pressed on a line.
 *
 * Widths are measured from the card's edge inward, so moving the right line to
 * the right *shrinks* its width, and the bottom line down shrinks its width. An
 * arrow along the line's own length (up/down on a vertical line) does nothing.
 */
export function arrowDeltaMm(key: LineKey, direction: Direction, stepMm: number): number {
  switch (key) {
    case "left_px":
      return direction === "left" ? -stepMm : direction === "right" ? stepMm : 0;
    case "right_px":
      return direction === "right" ? -stepMm : direction === "left" ? stepMm : 0;
    case "top_px":
      return direction === "up" ? -stepMm : direction === "down" ? stepMm : 0;
    case "bottom_px":
      return direction === "down" ? -stepMm : direction === "up" ? stepMm : 0;
  }
}

/** The two arrows that move a line: across its own axis only. */
export function directionsFor(key: LineKey): [Direction, Direction] {
  return key === "left_px" || key === "right_px" ? ["left", "right"] : ["up", "down"];
}

/**
 * The four centering lines and their drag handles, drawn over the analysed
 * photo.
 *
 * Absolutely positioned to fill its parent, which is the same `relative`
 * container holding the photo and `RegionOverlay` -- so this element's bounding
 * rect *is* the displayed photo's, and pointer positions convert straight into
 * raster pixels against it.
 *
 * Rendered after `RegionOverlay` so the handles sit above its numbered badges;
 * a badge landing on a handle would otherwise swallow the drag.
 *
 * While a handle is dragged -- or a line is selected for nudging -- a loupe
 * shows the photo magnified around the line, beside the pointer rather than
 * under it. It reads the same photo as a CSS background, so it costs no second
 * fetch, and its zoom is capped by what that photo actually holds.
 */
export default function CenteringLines({
  widths,
  raster,
  enabled,
  handleLabels,
  onDrag,
  variant = "detected",
  photoUrl = null,
  selected = null,
  onSelect,
  onNudge,
  pxPerMm = 0,
  boundsMm,
}: {
  widths: CenteringWidths;
  raster: { w: number; h: number };
  /** False when adjustment is off -- lines still draw, so the customer can see
   *  where the border is, but nothing moves. */
  enabled: boolean;
  handleLabels: Record<LineKey, string>;
  onDrag: (key: LineKey, rasterPx: number) => void;
  /** "placed" draws lines the customer placed by hand: dashed pink, so a
   *  placement can never be mistaken for a measurement at a glance. */
  variant?: "detected" | "placed";
  /** The displayed photo, for the loupe. No loupe without it. */
  photoUrl?: string | null;
  selected?: LineKey | null;
  onSelect?: (key: LineKey) => void;
  /** Keyboard nudge, in millimetres of border width (see `arrowDeltaMm`). */
  onNudge?: (key: LineKey, mm: number) => void;
  pxPerMm?: number;
  boundsMm?: (key: LineKey) => [number, number];
}) {
  const boxRef = useRef<HTMLDivElement>(null);
  const [box, setBox] = useState<{ w: number; h: number } | null>(null);
  const [dragKey, setDragKey] = useState<LineKey | null>(null);
  const [pointer, setPointer] = useState<{ x: number; y: number } | null>(null);

  // The loupe needs the box's CSS size while rendering, and a ref read during
  // render is stale by definition -- so it is tracked in state.
  useEffect(() => {
    const el = boxRef.current;
    if (!el) return;
    const observer = new ResizeObserver(([entry]) =>
      setBox({ w: entry.contentRect.width, h: entry.contentRect.height })
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  // Fractions of the raster, which is the space the overlay is positioned in.
  const fx = widths.left_px / raster.w;
  const fr = 1 - widths.right_px / raster.w;
  const fy = widths.top_px / raster.h;
  const fb = 1 - widths.bottom_px / raster.h;
  const lineFraction: Record<LineKey, number> = { left_px: fx, right_px: fr, top_px: fy, bottom_px: fb };

  const position: Record<LineKey, { left: string; top: string }> = {
    left_px: { left: `${fx * 100}%`, top: "50%" },
    right_px: { left: `${fr * 100}%`, top: "50%" },
    top_px: { left: "50%", top: `${fy * 100}%` },
    bottom_px: { left: "50%", top: `${fb * 100}%` },
  };

  const lines: { key: LineKey; x1: number; y1: number; x2: number; y2: number }[] = [
    { key: "left_px", x1: fx, y1: 0, x2: fx, y2: 1 },
    { key: "right_px", x1: fr, y1: 0, x2: fr, y2: 1 },
    { key: "top_px", x1: 0, y1: fy, x2: 1, y2: fy },
    { key: "bottom_px", x1: 0, y1: fb, x2: 1, y2: fb },
  ];

  /** The photo is scaled from the raster, so the pointer is converted back into
   *  raster pixels rather than CSS pixels -- otherwise the millimetre bounds
   *  would mean something different on every screen. */
  function toRasterPx(key: LineKey, clientX: number, clientY: number, rect: DOMRect): number {
    if (key === "left_px") return ((clientX - rect.left) / rect.width) * raster.w;
    if (key === "right_px") return ((rect.right - clientX) / rect.width) * raster.w;
    if (key === "top_px") return ((clientY - rect.top) / rect.height) * raster.h;
    return ((rect.bottom - clientY) / rect.height) * raster.h;
  }

  function handleMove(event: ReactPointerEvent<HTMLSpanElement>) {
    if (!dragKey || !boxRef.current) return;
    const rect = boxRef.current.getBoundingClientRect();
    setPointer({ x: event.clientX - rect.left, y: event.clientY - rect.top });
    onDrag(dragKey, toRasterPx(dragKey, event.clientX, event.clientY, rect));
  }

  function endDrag(event: ReactPointerEvent<HTMLSpanElement>) {
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
    setDragKey(null);
    setPointer(null);
  }

  function handleKeyDown(key: LineKey, event: ReactKeyboardEvent<HTMLSpanElement>) {
    const direction = ARROW_KEYS[event.key];
    if (!direction || !onNudge) return;
    const mm = arrowDeltaMm(key, direction, event.shiftKey ? 1 : 0.1);
    if (mm === 0) return;
    // Arrows would otherwise scroll the page as well as move the line.
    event.preventDefault();
    onNudge(key, mm);
  }

  // Where the loupe looks and where it sits, in the box's CSS pixels.
  const loupeKey = dragKey ?? selected;
  const loupe = (() => {
    if (!enabled || !loupeKey || !photoUrl || !box) return null;
    const vertical = loupeKey === "left_px" || loupeKey === "right_px";
    // Along the line: under the pointer while dragging, the handle otherwise.
    const along = dragKey && pointer ? (vertical ? pointer.y : pointer.x) : vertical ? box.h / 2 : box.w / 2;
    const cx = vertical ? lineFraction[loupeKey] * box.w : along;
    const cy = vertical ? along : lineFraction[loupeKey] * box.h;
    const zoom = Math.min(MAX_LOUPE_ZOOM, Math.max(1, (2 * raster.w) / box.w));
    const above = cy - LOUPE_GAP_PX - LOUPE_PX;
    // Flip below the line near the top of the photo; keep at least half of it
    // over the photo horizontally.
    const top = above >= 0 ? above : cy + LOUPE_GAP_PX;
    const left = Math.min(Math.max(cx - LOUPE_PX / 2, -LOUPE_PX / 2), box.w - LOUPE_PX / 2);
    return { vertical, cx, cy, zoom, top, left };
  })();

  return (
    <div ref={boxRef} className="absolute inset-0 touch-none select-none">
      <svg
        viewBox="0 0 1 1"
        preserveAspectRatio="none"
        className="pointer-events-none absolute inset-0 h-full w-full"
      >
        {lines.map((l) =>
          variant === "placed" ? (
            <line
              key={l.key}
              x1={l.x1}
              y1={l.y1}
              x2={l.x2}
              y2={l.y2}
              stroke="var(--neon-pink)"
              strokeWidth={2}
              strokeDasharray="6 4"
              vectorEffect="non-scaling-stroke"
            />
          ) : (
            <line
              key={l.key}
              x1={l.x1}
              y1={l.y1}
              x2={l.x2}
              y2={l.y2}
              stroke={selected === l.key ? "var(--neon-pink)" : "var(--grade-gem)"}
              strokeWidth={0.004}
            />
          )
        )}
      </svg>

      {enabled &&
        HANDLES.map((h) => {
          const mm = pxPerMm > 0 ? Math.round((widths[h.key] / pxPerMm) * 10) / 10 : null;
          const [minMm, maxMm] = boundsMm ? boundsMm(h.key) : [undefined, undefined];
          const isSelected = selected === h.key;
          return (
            <span
              key={h.key}
              role="slider"
              aria-label={handleLabels[h.key]}
              aria-orientation={h.key === "left_px" || h.key === "right_px" ? "horizontal" : "vertical"}
              aria-valuenow={mm ?? Math.round(widths[h.key])}
              aria-valuemin={minMm}
              aria-valuemax={maxMm}
              aria-valuetext={mm !== null ? `${mm} mm` : undefined}
              tabIndex={0}
              onFocus={() => onSelect?.(h.key)}
              onKeyDown={(e) => handleKeyDown(h.key, e)}
              onPointerDown={(e) => {
                e.currentTarget.setPointerCapture(e.pointerId);
                setDragKey(h.key);
                onSelect?.(h.key);
                const rect = boxRef.current?.getBoundingClientRect();
                if (rect) setPointer({ x: e.clientX - rect.left, y: e.clientY - rect.top });
              }}
              onPointerMove={handleMove}
              onPointerUp={endDrag}
              onPointerCancel={endDrag}
              // 44px of transparent hit area around a 20px dot: the dot marks
              // where the line sits, so it stays small, and the target does not.
              className="absolute flex h-11 w-11 -translate-x-1/2 -translate-y-1/2 touch-none items-center justify-center"
              style={{ left: position[h.key].left, top: position[h.key].top, cursor: h.cursor }}
            >
              <span
                aria-hidden="true"
                className="h-5 w-5 rounded-full border-2 border-white shadow-md"
                style={{ backgroundColor: isSelected ? "var(--neon-pink)" : "var(--grade-gem)" }}
              />
            </span>
          );
        })}

      {loupe && box && (
        <div
          aria-hidden="true"
          className="pointer-events-none absolute overflow-hidden rounded-full shadow-lg"
          style={{
            width: LOUPE_PX,
            height: LOUPE_PX,
            left: loupe.left,
            top: loupe.top,
            // An outline rather than a border, so the background's origin is the
            // circle's own edge and the maths below needs no inset.
            outline: "3px solid white",
            backgroundImage: `url(${photoUrl})`,
            backgroundRepeat: "no-repeat",
            backgroundSize: `${box.w * loupe.zoom}px ${box.h * loupe.zoom}px`,
            backgroundPosition: `${LOUPE_PX / 2 - loupe.cx * loupe.zoom}px ${LOUPE_PX / 2 - loupe.cy * loupe.zoom}px`,
          }}
        >
          <span
            className="absolute"
            style={
              loupe.vertical
                ? { left: LOUPE_PX / 2 - 1, top: 0, bottom: 0, width: 2, backgroundColor: "var(--neon-pink)" }
                : { top: LOUPE_PX / 2 - 1, left: 0, right: 0, height: 2, backgroundColor: "var(--neon-pink)" }
            }
          />
          <span
            className="absolute h-2 w-2 -translate-x-1/2 -translate-y-1/2 rounded-full border border-white"
            style={{ left: LOUPE_PX / 2, top: LOUPE_PX / 2 }}
          />
        </div>
      )}
    </div>
  );
}
