/**
 * How a score is shown, in the one place both scorecards read from.
 *
 * Lifted out of `SubmissionOverview` when the public share page gained its own
 * renderer. The two views are deliberately separate components -- one fetches
 * every image with a Bearer token, the other uses plain public URLs -- but a
 * card scoring 9.6 must not be "mint" on the customer's page and "gem" on the
 * page they showed a buyer.
 *
 * The score itself is never computed here. That lives in `analysis/scoring.py`,
 * and a second copy in TypeScript is the divergence `recompute.py` has already
 * demonstrated twice.
 */

export const CATEGORY_ORDER = ["centering", "corners", "edges", "surface"] as const;

export const SEVERITY_COLOR: Record<string, "success" | "warning" | "danger"> = {
  none: "success",
  minor: "warning",
  major: "danger",
};

/**
 * Which grade-tier colour a score wears.
 *
 * Thresholds are a judgment call: the backend has no discrete "grade" concept,
 * only a continuous raw_score per category, so these map that score onto the
 * synthwave palette (--grade-gem/mint/warn). Compared against the same
 * one-decimal rounding used for display, not the raw float, so a score that
 * *displays* as "9.5" cannot fall on the wrong side of the 9.5 threshold from
 * floating-point noise below the digit anybody can see.
 */
export function gradeTierClass(score: number): string {
  const rounded = Math.round(score * 10) / 10;
  if (rounded >= 9.9) return "grade-gem";
  if (rounded >= 9.5) return "grade-mint";
  return "grade-warn";
}
