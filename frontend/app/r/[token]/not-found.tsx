import PublicReportNotFound from "./not-found-client";

/** Reached for an unknown token, one that was rotated away, and a report that
 *  is no longer published -- deliberately indistinguishable. Telling them apart
 *  would confirm to somebody guessing tokens that they had found a real one. */
export default function NotFound() {
  return <PublicReportNotFound />;
}
