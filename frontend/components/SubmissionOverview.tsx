import type { Comparison, SubmissionDetail } from "@/lib/api";
import StatusBadge from "./StatusBadge";

const CATEGORY_ORDER = ["centering", "corners", "edges", "surface"];
const SEVERITY_STYLES: Record<string, string> = {
  none: "badge-success",
  minor: "badge-warning",
  major: "badge-danger",
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
      <div className="card">
        <div className="flex-row">
          <div>
            <h2>{submission.card?.card_name ?? "Unknown card"}</h2>
            <p className="muted">
              {submission.card?.game}
              {submission.card?.set_name ? ` — ${submission.card.set_name}` : ""}
              {submission.card?.card_number ? ` — #${submission.card.card_number}` : ""}
              {submission.card?.foil ? " — Foil" : ""}
            </p>
          </div>
          <StatusBadge status={submission.status} />
        </div>

        {combinedByCategory.size > 0 && (
          <div className="score-grid">
            {CATEGORY_ORDER.filter((c) => combinedByCategory.has(c)).map((category) => {
              const result = combinedByCategory.get(category)!;
              const lowerConfidence = Boolean(result.flags?.lower_confidence);
              return (
                <div className="score-tile" key={category}>
                  <div className="muted" style={{ textTransform: "capitalize", fontSize: "0.82rem" }}>
                    {category}
                    {lowerConfidence && (
                      <span className="badge badge-warning" style={{ marginLeft: 6 }}>
                        lower confidence
                      </span>
                    )}
                  </div>
                  <div className="value">{result.raw_score.toFixed(1)}</div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {comparisonsByCategory.size > 0 && (
        <div className="card">
          <h3>Multi-company comparison</h3>
          <p className="muted" style={{ marginTop: 6, fontSize: "0.88rem" }}>
            Points of contention that may affect how each company treats this card. This is not a
            predicted numeric grade from any company.
          </p>
          {CATEGORY_ORDER.filter((c) => comparisonsByCategory.has(c)).map((category) => (
            <div key={category} style={{ marginTop: 18 }}>
              <h3 style={{ textTransform: "capitalize", fontSize: "0.95rem" }}>{category}</h3>
              <table>
                <thead>
                  <tr>
                    <th>Company</th>
                    <th>Assessment</th>
                    <th>Notes</th>
                  </tr>
                </thead>
                <tbody>
                  {comparisonsByCategory.get(category)!.map((comp) => (
                    <tr key={`${comp.company}-${comp.category}`}>
                      <td>{comp.company}</td>
                      <td>
                        <span className={`badge ${SEVERITY_STYLES[comp.severity]}`}>{comp.severity}</span>
                      </td>
                      <td style={{ fontSize: "0.88rem" }}>{comp.contention_note}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ))}
        </div>
      )}
    </>
  );
}
