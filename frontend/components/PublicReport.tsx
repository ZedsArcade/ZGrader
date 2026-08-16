"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { Card, Chip, Table, buttonVariants, cn } from "@heroui/react";
import * as api from "@/lib/api";
import { CATEGORY_ORDER, SEVERITY_COLOR, gradeTierClass } from "@/lib/grade-display";
import { useLocale, useTranslations } from "@/lib/i18n/context";
import { ratiosFromWidths } from "@/lib/use-centering-adjust";
import RegionOverlay, { type CategoryRegion } from "./RegionOverlay";

/**
 * A shared report as a stranger sees it.
 *
 * Separate from `SubmissionOverview` rather than a read-only mode of it, and
 * the reason is load-bearing rather than cosmetic: that component takes a
 * Bearer token and fetches every image through `fetchAuthedImage` into a blob,
 * because the authenticated image routes need a header. Here the share token in
 * the path is the whole credential, so the images are plain `<img src>` against
 * a public URL -- which is also what lets Cloudflare cache them, the thing that
 * keeps a viral link off a home server running OpenCV.
 *
 * Nothing here is interactive. There is no dismissing a finding and no dragging
 * a centering line: those change a stored score, and the person reading this
 * page is not the person entitled to change it.
 */

const SIDES: api.ScanSide[] = ["front", "back"];

/** Replaces {companies} with the operator's *enabled* list, which arrives on
 *  the payload rather than from the branding context -- one fetch, and the same
 *  source that decides which companies the comparison table shows.
 *
 *  The locale is passed explicitly and must be: `Intl.ListFormat` defaults to
 *  the *browser's* locale, not the app's, which put "PSA, BGS, CGC, TAG and
 *  ACE" in the middle of a Spanish sentence. `useGradingCompanies` gets this
 *  right and this is the same argument for the same reason. */
function withCompanies(
  text: string,
  companies: string[],
  fallback: string,
  locale: string
): string {
  const list =
    companies.length === 0
      ? fallback
      : new Intl.ListFormat(locale, { style: "long", type: "conjunction" }).format(companies);
  return text.replace("{companies}", list);
}

/**
 * One side's photo, with the markings drawn over it.
 *
 * Its own component because the centering frame has to be remapped against the
 * raster's real pixel dimensions, and those are only known once the image has
 * loaded -- so this needs state that the page as a whole does not.
 */
function SidePhoto({
  shareToken,
  side,
  regions,
  markers,
  applied,
  alt,
}: {
  shareToken: string;
  side: api.ScanSide;
  regions: CategoryRegion[];
  markers: CategoryRegion[];
  /** The centering adjustment for this side, if the owner made one. */
  applied: api.CenteringWidths | null;
  alt: string;
}) {
  const [raster, setRaster] = useState<{ w: number; h: number } | null>(null);
  const imgRef = useRef<HTMLImageElement>(null);

  // `onLoad` alone is not enough here, and the difference from AnnotatedPhoto is
  // the reason. There the src is a blob URL assigned after a fetch, so the load
  // always happens under React. Here the <img> ships in the server HTML, so the
  // browser can finish loading it *before* hydration attaches the handler --
  // `onLoad` then never fires, `raster` stays null, and the frame silently falls
  // back to the detected box. It fails on a warm cache and passes on a cold one,
  // which is the worst way for this particular bug to behave.
  useEffect(() => {
    const el = imgRef.current;
    if (el?.complete && el.naturalWidth > 0) {
      setRaster({ w: el.naturalWidth, h: el.naturalHeight });
    }
  }, []);

  // The centering frame is built server-side from the *detected* border, and
  // the stored measurement deliberately keeps holding that -- clearing an
  // adjustment has to restore the detected figures with no other trace. So the
  // adjustment is applied at render time, here, exactly as AnnotatedPhoto does
  // it for the owner's own view.
  //
  // Skipping this would draw detection's frame beside a score derived from
  // where the customer put the lines: the report contradicting itself, on the
  // one page that gets shown to somebody deciding whether to buy the card.
  const drawn: CategoryRegion[] =
    applied && raster
      ? regions.map((region) => {
          if (region.category !== "centering") return region;
          const { left_px, right_px, top_px, bottom_px } = applied;
          // Mirrors regions._build_centering_regions: the box runs from the
          // border inward on every side.
          const bbox: [number, number, number, number] = [
            left_px / raster.w,
            top_px / raster.h,
            (raster.w - right_px) / raster.w,
            (raster.h - bottom_px) / raster.h,
          ];
          return { ...region, bbox_norm: bbox, anchor_norm: [bbox[0], bbox[1]] as [number, number] };
        })
      : regions;
  const drawnMarkers = drawn.filter((region) =>
    markers.some((m) => m.category === region.category && m.id === region.id)
  );

  return (
    <div className="relative inline-block max-w-md self-center">
      {/* No token, no blob dance, no object URL: a public URL goes straight
          into src and gets cached at the edge. */}
      <img
        ref={imgRef}
        src={api.publicImageUrl(shareToken, side, "base")}
        alt={alt}
        className="w-full rounded-lg border border-border"
        // Kept alongside the mount check above: this covers the image that is
        // still in flight when hydration happens, that one covers the image
        // that already finished.
        onLoad={(e) =>
          setRaster({ w: e.currentTarget.naturalWidth, h: e.currentTarget.naturalHeight })
        }
      />
      <RegionOverlay
        regions={drawn}
        markers={drawnMarkers}
        side={side}
        // Nothing is dismissable here, and a dismissed finding is already
        // excluded server-side, so there is nothing to draw muted.
        dismissedRegions={new Set()}
      />
    </div>
  );
}

export default function PublicReport({
  report,
  shareToken,
}: {
  report: api.PublicReport;
  shareToken: string;
}) {
  const t = useTranslations();
  const { locale } = useLocale();
  const combinedByCategory = new Map(
    report.results.filter((r) => r.side === "combined").map((r) => [r.category, r])
  );
  const resultsBySide = new Map(
    SIDES.map((side) => [side, report.results.filter((r) => r.side === side)])
  );
  const comparisonsByCategory = new Map<string, api.Comparison[]>();
  for (const comparison of report.comparisons) {
    const list = comparisonsByCategory.get(comparison.category) ?? [];
    list.push(comparison);
    comparisonsByCategory.set(comparison.category, list);
  }
  // Derived from the results actually being rendered rather than from
  // `report.sides`, which counts registered scans. The side is only worth
  // naming beside a ratio when there is another one to tell it apart from.
  const bothSidesMeasured = SIDES.filter((s) => (resultsBySide.get(s)?.length ?? 0) > 0).length > 1;

  return (
    <div className="flex flex-col gap-5">
      {/* Above the scores, not below them. Almost everyone reading this page
          arrived from a link in a chat and has never seen the site, so "this is
          not a grading company" has to be legible before the numbers are, not
          in a footnote after them. */}
      <Card>
        <Card.Header>
          <Card.Title>{t.publicReport.whatThisIsTitle}</Card.Title>
        </Card.Header>
        <Card.Content className="flex flex-col gap-2">
          <p className="text-sm leading-relaxed text-muted">{t.publicReport.whatThisIsBody}</p>
          <p className="text-sm leading-relaxed text-muted">
            {withCompanies(
              t.publicReport.notAffiliated,
              report.grading_companies,
              t.landing.companiesFallback,
              locale
            )}
          </p>
        </Card.Content>
      </Card>

      {/* Never conditional on anything but the fact itself. A report the owner
          adjusted has to say so wherever it is read, and a page shown to a
          buyer is the one place hiding it would actually pay. */}
      {report.client_adjusted && (
        <Card className="border-2" style={{ borderColor: "var(--neon-pink)" }}>
          <Card.Content>
            <p className="text-sm font-semibold" style={{ color: "var(--neon-pink)" }}>
              ⚠ {t.publicReport.adjustedTitle}
            </p>
            <p className="mt-1 text-sm text-muted">
              {t.publicReport.adjustedBody.replace("{count}", String(report.dismissed_count))}
            </p>
          </Card.Content>
        </Card>
      )}

      <Card>
        <Card.Content>
          <h1 className="text-lg font-semibold text-foreground">
            {report.card?.card_name ?? t.submissionDetail.unknownCard}
          </h1>
          <p className="text-sm text-muted">
            {report.card?.game}
            {report.card?.set_name ? ` — ${report.card.set_name}` : ""}
            {report.card?.card_number ? ` — #${report.card.card_number}` : ""}
            {report.card?.foil ? ` — ${t.submissionDetail.foilLabel}` : ""}
          </p>
          <p className="mt-1 text-xs text-muted">
            {/* Locale passed explicitly, for the same reason as the company
                list above: the bare call formats to the browser's locale, so a
                Spanish page would date the check in the reader's format rather
                than the one the rest of the sentence is written in. */}
            {t.publicReport.checkedOn} {new Date(report.created_at).toLocaleDateString(locale)}
          </p>

          {combinedByCategory.size > 0 && (
            <div className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-4">
              {CATEGORY_ORDER.filter((c) => combinedByCategory.has(c)).map((category) => {
                const result = combinedByCategory.get(category)!;
                // Null is "we could not tell", not "this is terrible". Showing
                // a zero here would be the confident wrongness the nullable
                // score exists to remove -- on the page most likely to be shown
                // to somebody deciding whether to buy the card.
                const unmeasurable = result.raw_score === null;
                const limitationCodes = result.measurements.assessment?.limitations ?? [];
                return (
                  <div
                    key={category}
                    className="rounded-xl border border-border bg-surface-secondary p-3"
                  >
                    <div className="flex flex-wrap items-center gap-1.5 text-xs text-muted">
                      {t.category[category]}
                      {result.flags.lower_confidence && (
                        <Chip color="warning" variant="soft" size="sm">
                          {t.submissionDetail.lowerConfidence}
                        </Chip>
                      )}
                    </div>
                    <div className="mt-1">
                      {unmeasurable ? (
                        <div className="inline-flex rounded-lg px-2 py-0.5 text-lg font-semibold text-muted">
                          {t.submissionDetail.unmeasurable}
                        </div>
                      ) : (
                        <div
                          className={`inline-flex rounded-lg px-2 py-0.5 text-2xl font-semibold ${gradeTierClass(result.raw_score!)}`}
                        >
                          {result.raw_score!.toFixed(1)}
                        </div>
                      )}
                    </div>
                    {/* The measurement behind the number, in the form a
                        collector actually thinks in: "47/53" says more at a
                        glance than 7.9 does. Derived from the widths as
                        adjusted, so it cannot contradict the score beside it. */}
                    {category === "centering" && !unmeasurable && (
                      <div className="mt-1.5 flex flex-col gap-0.5">
                        {SIDES.map((side) => {
                          const centering = (resultsBySide.get(side) ?? []).find(
                            (r) => r.category === "centering"
                          );
                          if (!centering) return null;
                          const m = centering.measurements;
                          if (m.left_px === null || m.top_px === null) return null;
                          const widths = {
                            left_px: m.left_px ?? 0,
                            right_px: m.right_px ?? 0,
                            top_px: m.top_px ?? 0,
                            bottom_px: m.bottom_px ?? 0,
                            ...(report.centering_adjustments?.[side] ?? {}),
                          };
                          const { lr, tb } = ratiosFromWidths(widths);
                          const pair = (r: [number, number]) =>
                            `${Math.round(r[0])}/${Math.round(r[1])}`;
                          // An axis needs both of its sides. Without this guard
                          // a missing side reads as a confident 50/50 for an
                          // axis that was never measured.
                          const axes: [string, [number, number]][] = [];
                          if (widths.left_px + widths.right_px > 0) {
                            axes.push([t.submissionDetail.leftRightShort, lr]);
                          }
                          if (widths.top_px + widths.bottom_px > 0) {
                            axes.push([t.submissionDetail.topBottomShort, tb]);
                          }
                          if (axes.length === 0) return null;
                          return (
                            <p key={side} className="text-[11px] leading-snug text-muted">
                              {bothSidesMeasured && <span>{t.breakout[side]} </span>}
                              {axes.map(([label, ratio], i) => (
                                <span key={label}>
                                  {i > 0 && <span className="px-1">·</span>}
                                  {label}{" "}
                                  <span className="font-medium tabular-nums text-foreground">
                                    {pair(ratio)}
                                  </span>
                                </span>
                              ))}
                            </p>
                          );
                        })}
                      </div>
                    )}
                    {limitationCodes.length > 0 && (
                      <ul className="mt-1.5 flex flex-col gap-1">
                        {limitationCodes.map((code) => {
                          const text =
                            t.submissionDetail.limitation[
                              code as keyof typeof t.submissionDetail.limitation
                            ];
                          // An unknown code means the backend added one without
                          // copy. Render nothing rather than a raw identifier.
                          return text ? (
                            <li key={code} className="text-[11px] leading-snug text-muted">
                              {text}
                            </li>
                          ) : null;
                        })}
                      </ul>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </Card.Content>
      </Card>

      {SIDES.filter((side) => (resultsBySide.get(side)?.length ?? 0) > 0).map((side) => {
        const results = resultsBySide.get(side)!;
        const regions: CategoryRegion[] = results.flatMap((result) =>
          // A category that could not be measured draws no overlay: every region
          // severity is a claim, and "ok" asserts that part of the card was
          // checked and is clean.
          result.raw_score === null
            ? []
            : result.measurements.regions.map((region) => ({ ...region, category: result.category }))
        );
        const flagged = regions.filter((region) => region.severity === "flag");
        const observations = results.flatMap((r) => r.measurements.ai_observations);
        return (
          <Card key={side}>
            <Card.Header>
              <Card.Title>
                {t.submissionDetail.photoTitle} — {t.breakout[side]}
              </Card.Title>
            </Card.Header>
            <Card.Content className="flex flex-col gap-3">
              <SidePhoto
                shareToken={shareToken}
                side={side}
                regions={regions}
                markers={flagged}
                applied={report.centering_adjustments?.[side] ?? null}
                alt={`${t.submissionDetail.photoTitle} — ${t.breakout[side]}`}
              />
              {flagged.length > 0 && (
                <ol className="flex flex-col gap-1">
                  {flagged.map((region, i) => (
                    <li key={`${region.category}:${region.id}`} className="text-xs text-muted">
                      <span className="font-semibold text-foreground">{i + 1}.</span>{" "}
                      {region.note ?? t.category[region.category as keyof typeof t.category]}
                    </li>
                  ))}
                </ol>
              )}
              {flagged.length === 0 && (
                <p className="text-xs text-muted">{t.breakout.noRegionsNote}</p>
              )}
              {observations.map((observation, i) => (
                <p key={i} className="text-xs leading-relaxed text-muted">
                  {observation.note}
                </p>
              ))}
            </Card.Content>
          </Card>
        );
      })}

      {comparisonsByCategory.size > 0 && (
        <Card>
          <Card.Header>
            <Card.Title>{t.submissionDetail.comparisonTitle}</Card.Title>
            <Card.Description>{t.submissionDetail.comparisonSubtitle}</Card.Description>
          </Card.Header>
          <Card.Content className="flex flex-col gap-6">
            {CATEGORY_ORDER.filter((c) => comparisonsByCategory.has(c)).map((category) => (
              <div key={category}>
                <h3 className="mb-2 text-sm font-semibold text-foreground">
                  {t.category[category]}
                </h3>
                <Table>
                  {/* Wide content scrolls inside its own container, never the
                      page -- the site's no-horizontal-scroll rule. */}
                  <Table.ScrollContainer>
                    <Table.Content
                      aria-label={`${t.category[category]} ${t.submissionDetail.comparisonTitle}`}
                    >
                      <Table.Header>
                        <Table.Column isRowHeader>{t.submissionDetail.colCompany}</Table.Column>
                        <Table.Column>{t.submissionDetail.colAssessment}</Table.Column>
                        <Table.Column>{t.submissionDetail.colNotes}</Table.Column>
                      </Table.Header>
                      <Table.Body>
                        {comparisonsByCategory.get(category)!.map((comparison) => (
                          <Table.Row
                            key={`${comparison.company}-${comparison.category}`}
                            id={`${comparison.company}-${comparison.category}`}
                          >
                            <Table.Cell>{comparison.company}</Table.Cell>
                            <Table.Cell>
                              <Chip
                                color={SEVERITY_COLOR[comparison.severity]}
                                variant="soft"
                                size="sm"
                              >
                                {t.severity[comparison.severity as keyof typeof t.severity]}
                              </Chip>
                            </Table.Cell>
                            <Table.Cell className="text-sm">
                              {comparison.contention_note}
                            </Table.Cell>
                          </Table.Row>
                        ))}
                      </Table.Body>
                    </Table.Content>
                  </Table.ScrollContainer>
                </Table>
              </div>
            ))}
          </Card.Content>
        </Card>
      )}

      {/* Load-bearing for trust and stated publicly on /methodology too --
          surface analysis is lower-confidence by design and says so. */}
      <Card>
        <Card.Content className="flex flex-col gap-3">
          <p className="text-sm leading-relaxed text-muted">{t.publicReport.surfaceCaveat}</p>
          <Link
            href="/methodology"
            className="text-sm font-semibold text-accent link-accent-hover hover:underline"
          >
            {t.publicReport.methodologyLink} &rsaquo;
          </Link>
        </Card.Content>
      </Card>

      <Card className="interactive-card">
        <Card.Header>
          <Card.Title>{t.publicReport.ctaTitle}</Card.Title>
        </Card.Header>
        <Card.Content>
          <p className="text-sm text-muted">{t.publicReport.ctaBody}</p>
          <div className="mt-4">
            <Link
              href="/register"
              className={cn(buttonVariants({ variant: "primary" }), "btn-press btn-neon-hover")}
            >
              {t.publicReport.ctaButton}
            </Link>
          </div>
        </Card.Content>
      </Card>
    </div>
  );
}
