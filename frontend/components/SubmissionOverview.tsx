import { Card, Chip, Table } from "@heroui/react";
import type {
  AnalysisResult,
  Assessment,
  CenteringWidths,
  Comparison,
  ScanSide,
  SubmissionDetail,
} from "@/lib/api";
import { getDictionary, type Locale } from "@/lib/i18n/context";
import AnnotatedPhoto from "./AnnotatedPhoto";
import CenteringAdjuster from "./CenteringAdjuster";
import StatusBadge from "./StatusBadge";

const SIDES: ScanSide[] = ["front", "back"];

const CATEGORY_ORDER = ["centering", "corners", "edges", "surface"] as const;

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
function centeringHandles(
  results: AnalysisResult[]
): { detected: CenteringWidths; pxPerMm: number } | null {
  const result = results.find((r) => r.category === "centering");
  if (!result || result.raw_score === null) return null;
  const m = (result.measurements ?? {}) as Record<string, unknown>;
  const pxPerMm = (m.card_geometry as { px_per_mm?: number } | undefined)?.px_per_mm;
  if (typeof pxPerMm !== "number" || pxPerMm <= 0) return null;
  const widths = (["left_px", "right_px", "top_px", "bottom_px"] as const).map((k) => m[k]);
  if (!widths.every((v) => typeof v === "number")) return null;
  const [left_px, right_px, top_px, bottom_px] = widths as number[];
  return { detected: { left_px, right_px, top_px, bottom_px }, pxPerMm };
}
const SEVERITY_COLOR: Record<string, "success" | "warning" | "danger"> = {
  none: "success",
  minor: "warning",
  major: "danger",
};

// Thresholds are a judgment call: the backend has no discrete "grade"
// concept, only a continuous raw_score per category, so these map that
// score onto the synthwave grade-tier palette (--grade-gem/mint/warn).
// Compared against the same one-decimal rounding used for display (not the
// raw float), so a score that *displays* as "9.5" can't fall on the wrong
// side of the 9.5 threshold just from floating-point noise below that digit.
function gradeTierClass(score: number): string {
  const rounded = Math.round(score * 10) / 10;
  if (rounded >= 9.9) return "grade-gem";
  if (rounded >= 9.5) return "grade-mint";
  return "grade-warn";
}

export default function SubmissionOverview({
  submission,
  token,
  locale = "en",
  onToggleRegion,
  onAdjusted,
}: {
  submission: SubmissionDetail;
  token: string;
  locale?: Locale;
  onToggleRegion: (regionKey: string, dismissed: boolean) => void;
  /** Omitted by the read-only callers (the operator's admin view), which
   *  hides the handles rather than showing controls that do nothing. */
  onAdjusted?: (updated: SubmissionDetail) => void;
}) {
  const t = getDictionary(locale);
  const dismissedRegions = new Set(submission.dismissed_regions ?? []);
  const combinedByCategory = new Map(
    submission.analysis_results.filter((r) => r.side === "combined").map((r) => [r.category, r])
  );
  const comparisonsByCategory = new Map<string, Comparison[]>();
  for (const comp of submission.company_comparisons) {
    const list = comparisonsByCategory.get(comp.category) ?? [];
    list.push(comp);
    comparisonsByCategory.set(comp.category, list);
  }
  const resultsBySide = new Map<ScanSide, typeof submission.analysis_results>(
    SIDES.map((side) => [side, submission.analysis_results.filter((r) => r.side === side)])
  );

  return (
    <>
      {dismissedRegions.size > 0 && (
        <Card className="mb-5 border-2" style={{ borderColor: "var(--neon-pink)" }}>
          <Card.Content>
            <p className="text-sm font-semibold" style={{ color: "var(--neon-pink)" }}>
              ⚠ {t.submissionDetail.adjustedBannerTitle}
            </p>
            <p className="mt-1 text-sm text-muted">
              {t.submissionDetail.adjustedBannerBody.replace("{count}", String(dismissedRegions.size))}
            </p>
          </Card.Content>
        </Card>
      )}
      <Card>
        <Card.Content>
          <div className="flex items-start justify-between gap-4">
            <div>
              <h2 className="text-lg font-semibold text-foreground">
                {submission.card?.card_name ?? t.submissionDetail.unknownCard}
              </h2>
              <p className="text-sm text-muted">
                {submission.card?.game}
                {submission.card?.set_name ? ` — ${submission.card.set_name}` : ""}
                {submission.card?.card_number ? ` — #${submission.card.card_number}` : ""}
                {submission.card?.foil ? ` — ${t.submissionDetail.foilLabel}` : ""}
              </p>
            </div>
            <StatusBadge status={submission.status} locale={locale} />
          </div>

          {combinedByCategory.size > 0 && (
            <div className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-4">
              {CATEGORY_ORDER.filter((c) => combinedByCategory.has(c)).map((category) => {
                const result = combinedByCategory.get(category)!;
                const lowerConfidence = Boolean(result.flags?.lower_confidence);
                const original = (result.measurements?.original_raw_score as number | undefined) ?? null;
                // null score = unmeasurable. Never render it as 0: "we could
                // not tell" and "this is terrible" are different answers, and
                // showing the second is exactly the confident wrongness the
                // nullable score exists to remove.
                const unmeasurable = result.raw_score === null;
                // What actually constrained this reading. Shown under the
                // score rather than tucked into a footnote -- a caveat nobody
                // reads is the same as no caveat.
                const assessmentBlock = result.measurements?.assessment as Assessment | undefined;
                const limitationCodes: string[] = assessmentBlock?.limitations ?? [];
                const adjusted =
                  !unmeasurable &&
                  original !== null &&
                  Math.round(original * 10) !== Math.round(result.raw_score! * 10);
                return (
                  <div
                    key={category}
                    className="interactive-card verdict-reveal rounded-xl border border-border bg-surface-secondary p-3"
                  >
                    <div className="flex flex-wrap items-center gap-1.5 text-xs text-muted">
                      {t.category[category]}
                      {lowerConfidence && (
                        <Chip color="warning" variant="soft" size="sm">
                          {t.submissionDetail.lowerConfidence}
                        </Chip>
                      )}
                      {adjusted && (
                        <Chip color="danger" variant="soft" size="sm">
                          {t.submissionDetail.adjustedChip}
                        </Chip>
                      )}
                    </div>
                    <div className="mt-1 flex items-baseline gap-2">
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
                      {adjusted && (
                        <span className="text-xs text-muted line-through">
                          {t.submissionDetail.originalScorePrefix} {original!.toFixed(1)}
                        </span>
                      )}
                    </div>
                    {limitationCodes.length > 0 && (
                      <ul className="mt-1.5 flex flex-col gap-1">
                        {limitationCodes.map((code) => {
                          const text =
                            t.submissionDetail.limitation[
                              code as keyof typeof t.submissionDetail.limitation
                            ];
                          // An unknown code means the backend added one
                          // without copy. Render nothing rather than a raw
                          // identifier.
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

      {SIDES.filter((side) => (resultsBySide.get(side)?.length ?? 0) > 0).map((side) => (
        <Card className="mt-5" key={side}>
          <Card.Header>
            <Card.Title>
              {t.submissionDetail.photoTitle} — {t.breakout[side]}
            </Card.Title>
          </Card.Header>
          <Card.Content>
            <AnnotatedPhoto
              token={token}
              code={submission.submission_code}
              side={side}
              results={resultsBySide.get(side)!}
              dismissedRegions={dismissedRegions}
              onToggle={onToggleRegion}
            />
            {onAdjusted &&
              (() => {
                const handles = centeringHandles(resultsBySide.get(side)!);
                if (!handles) return null;
                return (
                  <div className="mt-4">
                    <CenteringAdjuster
                      token={token}
                      code={submission.submission_code}
                      side={side}
                      detected={handles.detected}
                      applied={submission.centering_adjustments?.[side] ?? null}
                      pxPerMm={handles.pxPerMm}
                      onAdjusted={onAdjusted}
                    />
                  </div>
                );
              })()}
          </Card.Content>
        </Card>
      ))}

      {comparisonsByCategory.size > 0 && (
        <Card className="mt-5">
          <Card.Header>
            <Card.Title>{t.submissionDetail.comparisonTitle}</Card.Title>
            <Card.Description>{t.submissionDetail.comparisonSubtitle}</Card.Description>
          </Card.Header>
          <Card.Content className="flex flex-col gap-6">
            {CATEGORY_ORDER.filter((c) => comparisonsByCategory.has(c)).map((category) => (
              <div key={category}>
                <h3 className="mb-2 text-sm font-semibold text-foreground">{t.category[category]}</h3>
                <Table>
                  <Table.ScrollContainer>
                    <Table.Content aria-label={`${t.category[category]} ${t.submissionDetail.comparisonTitle}`}>
                      <Table.Header>
                        <Table.Column isRowHeader>{t.submissionDetail.colCompany}</Table.Column>
                        <Table.Column>{t.submissionDetail.colAssessment}</Table.Column>
                        <Table.Column>{t.submissionDetail.colNotes}</Table.Column>
                      </Table.Header>
                      <Table.Body>
                        {comparisonsByCategory.get(category)!.map((comp) => (
                          <Table.Row key={`${comp.company}-${comp.category}`} id={`${comp.company}-${comp.category}`}>
                            <Table.Cell>{comp.company}</Table.Cell>
                            <Table.Cell>
                              <Chip color={SEVERITY_COLOR[comp.severity]} variant="soft" size="sm">
                                {t.severity[comp.severity as keyof typeof t.severity]}
                              </Chip>
                            </Table.Cell>
                            <Table.Cell className="text-sm">{comp.contention_note}</Table.Cell>
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
    </>
  );
}
