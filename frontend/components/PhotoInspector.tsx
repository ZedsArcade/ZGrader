"use client";

import { useEffect, useRef, useState, type PointerEvent as ReactPointerEvent, type WheelEvent } from "react";
import Button from "@/components/Button";
import RegionOverlay, { type CategoryRegion } from "@/components/RegionOverlay";
import { useTranslations } from "@/lib/i18n/context";
import * as api from "@/lib/api";

const MIN_ZOOM = 1;
const MAX_ZOOM = 8;
const ZOOM_STEP = 0.5;

/**
 * Fullscreen viewer for close inspection of an analysed photo: zoom, pan, and
 * a markings on/off toggle.
 *
 * Zoom/pan is a single CSS transform on a wrapper that contains both the photo
 * and the normalized SVG overlay, so the markings scale and pan in lockstep
 * with the image for free. Self-contained overlay (same approach as
 * ConfirmDialog) rather than depending on a HeroUI overlay API.
 */
export default function PhotoInspector({
  open,
  photoUrl,
  regions,
  markers,
  side,
  dismissedRegions,
  onClose,
}: {
  open: boolean;
  photoUrl: string;
  regions: CategoryRegion[];
  markers: CategoryRegion[];
  side: api.ScanSide;
  dismissedRegions: Set<string>;
  onClose: () => void;
}) {
  const t = useTranslations();
  const [zoom, setZoom] = useState(1);
  const [offset, setOffset] = useState({ x: 0, y: 0 });
  const [showMarkers, setShowMarkers] = useState(true);
  const dragStart = useRef<{ x: number; y: number; ox: number; oy: number } | null>(null);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  // Reset the view each time the inspector is opened.
  useEffect(() => {
    if (open) {
      setZoom(1);
      setOffset({ x: 0, y: 0 });
    }
  }, [open]);

  if (!open) return null;

  function clampZoom(next: number): number {
    return Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, next));
  }

  function changeZoom(delta: number) {
    setZoom((z) => {
      const next = clampZoom(z + delta);
      if (next === MIN_ZOOM) setOffset({ x: 0, y: 0 });
      return next;
    });
  }

  function handleWheel(event: WheelEvent<HTMLDivElement>) {
    changeZoom(event.deltaY < 0 ? ZOOM_STEP : -ZOOM_STEP);
  }

  function handlePointerDown(event: ReactPointerEvent<HTMLDivElement>) {
    if (zoom === MIN_ZOOM) return; // nothing to pan at fit-to-screen
    event.currentTarget.setPointerCapture(event.pointerId);
    dragStart.current = { x: event.clientX, y: event.clientY, ox: offset.x, oy: offset.y };
  }

  function handlePointerMove(event: ReactPointerEvent<HTMLDivElement>) {
    const start = dragStart.current;
    if (!start) return;
    setOffset({
      x: start.ox + (event.clientX - start.x),
      y: start.oy + (event.clientY - start.y),
    });
  }

  function handlePointerUp(event: ReactPointerEvent<HTMLDivElement>) {
    event.currentTarget.releasePointerCapture(event.pointerId);
    dragStart.current = null;
  }

  return (
    // The root is opaque: a translucent backdrop let the page's nav bar show
    // through and made the outline buttons unreadable. The toolbar keeps the
    // normal page surface (so themed button styles work in light and dark),
    // and only the viewing area goes dark -- a neutral backdrop is what you
    // want behind a card you're inspecting.
    <div role="dialog" aria-modal="true" className="fixed inset-0 z-50 flex flex-col bg-surface">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border bg-surface p-3">
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="outline" size="sm" onPress={() => changeZoom(ZOOM_STEP)}>
            {t.inspector.zoomIn}
          </Button>
          <Button variant="outline" size="sm" onPress={() => changeZoom(-ZOOM_STEP)}>
            {t.inspector.zoomOut}
          </Button>
          <Button
            variant="outline"
            size="sm"
            onPress={() => {
              setZoom(1);
              setOffset({ x: 0, y: 0 });
            }}
          >
            {t.inspector.resetZoom}
          </Button>
          <Button variant="outline" size="sm" onPress={() => setShowMarkers((s) => !s)}>
            {showMarkers ? t.inspector.hideMarkers : t.inspector.showMarkers}
          </Button>
          <span className="text-xs text-muted">{Math.round(zoom * 100)}%</span>
        </div>
        <Button variant="primary" size="sm" onPress={onClose}>
          {t.inspector.close}
        </Button>
      </div>

      <div
        className="relative flex-1 touch-none select-none overflow-hidden bg-black"
        onWheel={handleWheel}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        style={{ cursor: zoom > MIN_ZOOM ? "grab" : "default" }}
      >
        <div
          className="absolute inset-0 flex items-center justify-center"
          style={{
            transform: `translate(${offset.x}px, ${offset.y}px) scale(${zoom})`,
            transformOrigin: "center center",
          }}
        >
          <div className="relative">
            <img src={photoUrl} alt="" className="max-h-[85vh] max-w-[95vw] object-contain" draggable={false} />
            {showMarkers && (
              <RegionOverlay
                regions={regions}
                markers={markers}
                side={side}
                dismissedRegions={dismissedRegions}
              />
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
