"use client";

import RequireAuth from "@/components/RequireAuth";
import SubmissionView from "@/components/SubmissionView";

export default function SubmissionDetailClient({ code }: { code: string }) {
  return (
    <RequireAuth>
      <SubmissionView code={code} />
    </RequireAuth>
  );
}
