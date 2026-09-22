"use client";

import RequireAuth from "@/components/RequireAuth";
import SubmissionView from "@/components/SubmissionView";

/** The check page. Starts with no submission; the first photo creates one and
 *  the address becomes /dashboard/{code} without a remount (SubmissionView). */
export default function NewCheckPage() {
  return (
    <RequireAuth>
      <SubmissionView code={null} />
    </RequireAuth>
  );
}
