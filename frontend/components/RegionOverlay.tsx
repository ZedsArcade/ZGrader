"use client";

import * as api from "@/lib/api";

export interface CategoryRegion extends api.Region {
  category: string;
}

export function regionKey(region: CategoryRegion): string {
  return `${region.category}:${region.id}`;
}

// The persisted dismissal key includes the side (front/back), matching
// Submission.dismissed_regions and the toggle endpoint.
export function dismissKey(side: api.ScanSide, region: CategoryRegion): string {
  return `${side}:${region.category}:${region.id}`;
}

/**
 * The markings drawn over an analysed photo: a bounding box per region (or,
 * for an elongated defect like a crease, the segment itself) plus numbered
 * markers for the findings currently listed.
 *
 * Shared by the results page and the fullscreen inspector so both render
 * identically. Sits inside a `position: relative` wrapper that exactly bounds
 * the photo.
 */
export default function RegionOverlay({
  regions,
  markers,
  side,
  dismissedRegions,
}: {
  regions: CategoryRegion[];
  markers: CategoryRegion[];
  side: api.ScanSide;
  dismissedRegions: Set<string>;
}) {
  return (
    <>
      {/* preserveAspectRatio="none" makes the 0..1 viewBox map 1:1 onto the
          (non-square) photo -- correct for rects and lines, but it would
          distort a circle into an ellipse, so the numbered markers below are
          plain HTML positioned by percentage instead. */}
      <svg
        viewBox="0 0 1 1"
        preserveAspectRatio="none"
        className="pointer-events-none absolute inset-0 h-full w-full"
      >
        {regions.map((region) => {
          const isFlag = region.severity === "flag";
          // A low-confidence centering frame, or a region the client
          // dismissed, draws muted + dashed rather than asserting a solid
          // finding.
          const muted = region.low_confidence || dismissedRegions.has(dismissKey(side, region));
          const stroke = muted
            ? "var(--muted)"
            : isFlag
              ? "var(--neon-pink)"
              : "var(--grade-mint)";
          const dash = muted ? "0.02 0.015" : undefined;

          // An elongated defect carries the segment it was detected along;
          // its bounding box spans most of the card and pinpoints nothing,
          // so draw the line itself instead.
          if (region.line_norm) {
            const [lx0, ly0, lx1, ly1] = region.line_norm;
            return (
              <line
                key={regionKey(region)}
                x1={lx0}
                y1={ly0}
                x2={lx1}
                y2={ly1}
                stroke={stroke}
                strokeWidth={0.008}
                strokeDasharray={dash}
              />
            );
          }

          const [x0, y0, x1, y1] = region.bbox_norm;
          return (
            <rect
              key={regionKey(region)}
              x={x0}
              y={y0}
              width={x1 - x0}
              height={y1 - y0}
              fill="none"
              stroke={stroke}
              strokeWidth={isFlag ? 0.006 : 0.003}
              strokeDasharray={dash}
            />
          );
        })}
      </svg>
      {markers.map((region, i) => {
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
  );
}
