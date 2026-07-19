import { Card, Chip, Table } from "@heroui/react";
import type { Comparison, SubmissionDetail } from "@/lib/api";
import StatusBadge from "./StatusBadge";

const CATEGORY_ORDER = ["centering", "corners", "edges", "surface"];
const SEVERITY_COLOR: Record<string, "success" | "warning" | "danger"> = {
  none: "success",
  minor: "warning",
  major: "danger",
};

export default function SubmissionOverview({ submission }: { submission: SubmissionDetail }) {
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
                {submission.card?.card_name ?? "Unknown card"}
              </h2>
              <p className="text-sm text-muted">
                {submission.card?.game}
                {submission.card?.set_name ? ` — ${submission.card.set_name}` : ""}
                {submission.card?.card_number ? ` — #${submission.card.card_number}` : ""}
                {submission.card?.foil ? " — Foil" : ""}
              </p>
            </div>
            <StatusBadge status={submission.status} />
          </div>

          {combinedByCategory.size > 0 && (
            <div className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-4">
              {CATEGORY_ORDER.filter((c) => combinedByCategory.has(c)).map((category) => {
                const result = combinedByCategory.get(category)!;
                const lowerConfidence = Boolean(result.flags?.lower_confidence);
                return (
                  <div key={category} className="rounded-xl border border-border bg-surface-secondary p-3">
                    <div className="flex items-center gap-1.5 text-xs text-muted capitalize">
                      {category}
                      {lowerConfidence && (
                        <Chip color="warning" variant="soft" size="sm">
                          lower confidence
                        </Chip>
                      )}
                    </div>
                    <div className="mt-1 text-2xl font-semibold text-foreground">
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
            <Card.Title>Multi-company comparison</Card.Title>
            <Card.Description>
              Points of contention that may affect how each company treats this card. This is not
              a predicted numeric grade from any company.
            </Card.Description>
          </Card.Header>
          <Card.Content className="flex flex-col gap-6">
            {CATEGORY_ORDER.filter((c) => comparisonsByCategory.has(c)).map((category) => (
              <div key={category}>
                <h3 className="mb-2 text-sm font-semibold capitalize text-foreground">{category}</h3>
                <Table>
                  <Table.ScrollContainer>
                    <Table.Content aria-label={`${category} company comparison`}>
                      <Table.Header>
                        <Table.Column isRowHeader>Company</Table.Column>
                        <Table.Column>Assessment</Table.Column>
                        <Table.Column>Notes</Table.Column>
                      </Table.Header>
                      <Table.Body>
                        {comparisonsByCategory.get(category)!.map((comp) => (
                          <Table.Row key={`${comp.company}-${comp.category}`} id={`${comp.company}-${comp.category}`}>
                            <Table.Cell>{comp.company}</Table.Cell>
                            <Table.Cell>
                              <Chip color={SEVERITY_COLOR[comp.severity]} variant="soft" size="sm">
                                {comp.severity}
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
