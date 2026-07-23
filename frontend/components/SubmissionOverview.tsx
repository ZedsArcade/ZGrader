import { Card, Chip, Table } from "@heroui/react";
import type { Comparison, SubmissionDetail } from "@/lib/api";
import { getDictionary, type Locale } from "@/lib/i18n/context";
import StatusBadge from "./StatusBadge";

const CATEGORY_ORDER = ["centering", "corners", "edges", "surface"] as const;
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
  locale = "en",
}: {
  submission: SubmissionDetail;
  locale?: Locale;
}) {
  const t = getDictionary(locale);
  const combinedByCategory = new Map(
    submission.analysis_results.filter((r) => r.side === "combined").map((r) => [r.category, r])
  );
  const comparisonsByCategory = new Map<string, Comparison[]>();
  for (const comp of submission.company_comparisons) {
    const list = comparisonsByCategory.get(comp.category) ?? [];
    list.push(comp);
    comparisonsByCategory.set(comp.category, list);
  }

  return (
    <>
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
                return (
                  <div
                    key={category}
                    className="interactive-card verdict-reveal rounded-xl border border-border bg-surface-secondary p-3"
                  >
                    <div className="flex items-center gap-1.5 text-xs text-muted">
                      {t.category[category]}
                      {lowerConfidence && (
                        <Chip color="warning" variant="soft" size="sm">
                          {t.submissionDetail.lowerConfidence}
                        </Chip>
                      )}
                    </div>
                    <div
                      className={`mt-1 inline-flex rounded-lg px-2 py-0.5 text-2xl font-semibold ${gradeTierClass(result.raw_score)}`}
                    >
                      {result.raw_score.toFixed(1)}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </Card.Content>
      </Card>

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
