"use client";

import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { Chip } from "@heroui/react";
import Skeleton from "@/components/Skeleton";
import * as api from "@/lib/api";
import { useTranslations } from "@/lib/i18n/context";

interface CategoryRegion extends api.Region {
  category: string;
}

interface Line {
  key: string;
  x1: number;
  y1: number;
  x2: number;
  y2: number;
}

const SEVERITY_CHIP_COLOR: Record<api.Region["severity"], "success" | "danger"> = {
  ok: "success",
  flag: "danger",
};

function regionKey(region: CategoryRegion): string {
  return `${region.category}:${region.id}`;
}

// The persisted dismissal key includes the side (front/back), matching
// Submission.dismissed_regions and the toggle endpoint.
function dismissKey(side: api.ScanSide, region: CategoryRegion): string {
  return `${side}:${region.category}:${region.id}`;
}

// How many breakout panels/leader-lines show before the viewer expands the
// rest -- a card with a dozen-plus flags previously sprawled with leader
// lines crossing all over the photo. Worst-scoring regions come first (most
// useful), and the visible set is re-sorted top-to-bottom by photo position
// so panel order reads naturally and lines cross each other less.
const COLLAPSED_COUNT = 3;

export default function AnnotatedPhoto({
  token,
  code,
  side,
  results,
  dismissedRegions,
  onToggle,
}: {
  token: string;
  code: string;
  side: api.ScanSide;
  results: api.AnalysisResult[];
  dismissedRegions: Set<string>;
  onToggle: (regionKey: string, dismissed: boolean) => void;
}) {
  const t = useTranslations();
  const wrapperRef = useRef<HTMLDivElement>(null);
  const photoImgRef = useRef<HTMLImageElement>(null);
  const panelRefs = useRef<Map<string, HTMLDivElement>>(new Map());

  const [photoUrl, setPhotoUrl] = useState<string | null>(null);
  const [cropUrls, setCropUrls] = useState<Record<string, string>>({});
  const [lines, setLines] = useState<Line[]>([]);
  const [expanded, setExpanded] = useState(false);

  const allRegions: CategoryRegion[] = results.flatMap((r) => {
    const list = (r.measurements?.regions as api.Region[] | undefined) ?? [];
    return list.map((region) => ({ ...region, category: r.category }));
  });
  // Worst-scoring first for priority; the visible slice is re-sorted
  // top-to-bottom below so leader lines stay tidy.
  const ranked = allRegions
    .filter((r) => r.severity === "flag")
    .sort((a, b) => a.score - b.score);
  const visible = (expanded ? ranked : ranked.slice(0, COLLAPSED_COUNT)).sort(
    (a, b) => a.anchor_norm[1] - b.anchor_norm[1]
  );
  const hiddenCount = ranked.length - visible.length;

  useEffect(() => {
    let cancelled = false;
    const createdUrls: string[] = [];

    async function load() {
      try {
        const blob = await api.fetchAuthedImage(token, api.sidePhotoUrl(code, side));
        if (cancelled) return;
        const url = URL.createObjectURL(blob);
        createdUrls.push(url);
        setPhotoUrl(url);
      } catch {
        // No photo yet -- render nothing for the photo rather than a
        // broken-image icon; the panel list below still shows.
      }

      const entries = await Promise.all(
        // Fetch crops for every ranked region (not just the collapsed
        // slice) so expanding reveals already-loaded panels with no new
        // network round-trip. The set is bounded server-side.
        ranked.map(async (region) => {
          try {
            const blob = await api.fetchAuthedImage(
              token,
              api.regionCropUrl(code, side, region.category, region.id)
            );
            if (cancelled) return null;
            const url = URL.createObjectURL(blob);
            createdUrls.push(url);
            return [regionKey(region), url] as const;
          } catch {
            return null;
          }
        })
      );
      if (cancelled) return;
      setCropUrls(Object.fromEntries(entries.filter((e): e is [string, string] => e !== null)));
    }

    load();
    return () => {
      cancelled = true;
      createdUrls.forEach((url) => URL.revokeObjectURL(url));
    };
    // Only re-fetch when the submission/side identity actually changes --
    // `results`/`flagged` are derived fresh each render from the same
    // underlying data and would otherwise cause a fetch loop.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, code, side]);

  const recomputeLines = useCallback(() => {
    const wrapper = wrapperRef.current;
    const img = photoImgRef.current;
    if (!wrapper || !img) return;
    const wrapperRect = wrapper.getBoundingClientRect();
    const imgRect = img.getBoundingClientRect();

    const nextLines: Line[] = [];
    for (const region of visible) {
      const key = regionKey(region);
      const panel = panelRefs.current.get(key);
      if (!panel) continue;
      const panelRect = panel.getBoundingClientRect();
      const [ax, ay] = region.anchor_norm;
      nextLines.push({
        key,
        x1: imgRect.left - wrapperRect.left + ax * imgRect.width,
        y1: imgRect.top - wrapperRect.top + ay * imgRect.height,
        x2: panelRect.left - wrapperRect.left,
        y2: panelRect.top - wrapperRect.top + panelRect.height / 2,
      });
    }
    setLines(nextLines);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [photoUrl, cropUrls, expanded]);

  useLayoutEffect(() => {
    recomputeLines();
    window.addEventListener("resize", recomputeLines);
    const observer = new ResizeObserver(recomputeLines);
    if (wrapperRef.current) observer.observe(wrapperRef.current);
    panelRefs.current.forEach((el) => observer.observe(el));
    return () => {
      window.removeEventListener("resize", recomputeLines);
      observer.disconnect();
    };
  }, [recomputeLines]);

  if (!photoUrl && allRegions.length === 0) {
    return null;
  }

  return (
    <div
      ref={wrapperRef}
      className="relative grid grid-cols-1 items-start gap-4 lg:grid-cols-[1fr_320px]"
    >
      <div className="relative">
        {photoUrl ? (
          <img
            ref={photoImgRef}
            src={photoUrl}
            alt=""
            className="w-full rounded-xl border border-border"
            onLoad={recomputeLines}
          />
        ) : (
          <Skeleton className="aspect-[3/4] w-full rounded-xl" />
        )}
        {photoUrl && (
          <>
            {/* bbox outlines only -- SVG uses preserveAspectRatio="none" so
                a 0..1 viewBox maps 1:1 onto the (non-square) card photo,
                which is correct for axis-aligned rects but would visually
                distort a circle into an ellipse, so the numbered markers
                below are plain HTML instead, positioned by percentage. */}
            <svg
              viewBox="0 0 1 1"
              preserveAspectRatio="none"
              className="pointer-events-none absolute inset-0 h-full w-full"
            >
              {allRegions.map((region) => {
                const [x0, y0, x1, y1] = region.bbox_norm;
                const isFlag = region.severity === "flag";
                // A low-confidence centering frame, or a region the client
                // dismissed, draws muted + dashed rather than asserting a
                // solid finding box.
                const muted = region.low_confidence || dismissedRegions.has(dismissKey(side, region));
                return (
                  <rect
                    key={regionKey(region)}
                    x={x0}
                    y={y0}
                    width={x1 - x0}
                    height={y1 - y0}
                    fill="none"
                    stroke={muted ? "var(--muted)" : isFlag ? "var(--neon-pink)" : "var(--grade-mint)"}
                    strokeWidth={isFlag ? 0.006 : 0.003}
                    strokeDasharray={muted ? "0.02 0.015" : undefined}
                  />
                );
              })}
            </svg>
            {visible.map((region, i) => {
              const [ax, ay] = region.anchor_norm;
              return (
                <span
                  key={`marker-${regionKey(region)}`}
                  className="absolute flex h-5 w-5 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full text-xs font-semibold"
                  style={{
                    left: `${ax * 100}%`,
                    top: `${ay * 100}%`,
                    backgroundColor: "var(--neon-pink)",
                    color: "var(--neon-foreground)",
                  }}
                >
                  {i + 1}
                </span>
              );
            })}
          </>
        )}
      </div>

      {/* Leader lines from the photo to the panel rail -- desktop only; the
          panel list below carries matching numbered badges on all sizes, so
          mobile (no room for a literal diagram) still identifies each
          region via its number alone. */}
      {lines.length > 0 && (
        <svg className="pointer-events-none absolute inset-0 hidden h-full w-full lg:block">
          {lines.map((line) => (
            <line
              key={line.key}
              x1={line.x1}
              y1={line.y1}
              x2={line.x2}
              y2={line.y2}
              stroke="var(--neon-pink)"
              strokeWidth={1.5}
              opacity={0.6}
            />
          ))}
        </svg>
      )}

      <div className="verdict-reveal flex flex-col gap-3">
        {visible.length === 0 ? (
          <p className="text-sm text-muted">{t.breakout.noRegionsNote}</p>
        ) : (
          visible.map((region, i) => {
            const dKey = dismissKey(side, region);
            const isDismissed = dismissedRegions.has(dKey);
            return (
              <div
                key={regionKey(region)}
                ref={(el) => {
                  if (el) panelRefs.current.set(regionKey(region), el);
                  else panelRefs.current.delete(regionKey(region));
                }}
                className={`interactive-card flex flex-col gap-2 rounded-xl border border-border bg-surface-secondary p-3 ${
                  isDismissed ? "opacity-55" : ""
                }`}
              >
                <div className="flex items-center gap-2">
                  <span
                    className="inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-xs font-semibold"
                    style={{ backgroundColor: "var(--neon-pink)", color: "var(--neon-foreground)" }}
                  >
                    {i + 1}
                  </span>
                  <span
                    className={`text-sm font-semibold text-foreground ${isDismissed ? "line-through" : ""}`}
                  >
                    {t.category[region.category as keyof typeof t.category]}
                  </span>
                  <Chip size="sm" color={SEVERITY_CHIP_COLOR[region.severity]} variant="soft">
                    {region.severity === "flag" ? t.breakout.flaggedChip : t.breakout.okChip}
                  </Chip>
                  {isDismissed && (
                    <Chip size="sm" color="default" variant="soft">
                      {t.breakout.dismissedBadge}
                    </Chip>
                  )}
                  <button
                    type="button"
                    onClick={() => onToggle(dKey, !isDismissed)}
                    className="ml-auto text-xs font-semibold underline-offset-2 hover:underline"
                    style={{ color: "var(--neon-pink)" }}
                  >
                    {isDismissed ? t.breakout.restore : t.breakout.dismiss}
                  </button>
                </div>
                {cropUrls[regionKey(region)] && (
                  <img
                    src={cropUrls[regionKey(region)]}
                    alt={t.breakout.zoomedViewLabel}
                    className="h-40 w-full rounded-lg border border-border object-cover"
                  />
                )}
                {region.note && <p className="text-sm text-muted">{region.note}</p>}
                {region.low_confidence && (
                  <p className="text-xs italic text-muted">{t.breakout.lowConfidenceNote}</p>
                )}
              </div>
            );
          })
        )}
        {(hiddenCount > 0 || (expanded && ranked.length > COLLAPSED_COUNT)) && (
          <button
            type="button"
            onClick={() => setExpanded((e) => !e)}
            className="self-start text-sm font-semibold underline-offset-2 hover:underline"
            style={{ color: "var(--neon-pink)" }}
          >
            {expanded
              ? t.breakout.showLess
              : t.breakout.showMore.replace("{count}", String(hiddenCount))}
          </button>
        )}
      </div>
    </div>
  );
}
