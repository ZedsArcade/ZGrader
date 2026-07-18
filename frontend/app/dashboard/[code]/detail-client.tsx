"use client";

import { useEffect, useState } from "react";
import RequireAuth from "@/components/RequireAuth";
import SubmissionOverview from "@/components/SubmissionOverview";
import { useAuth } from "@/lib/auth-context";
import * as api from "@/lib/api";

function Detail({ code }: { code: string }) {
  const { token } = useAuth();
  const [submission, setSubmission] = useState<api.SubmissionDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [downloading, setDownloading] = useState(false);

  useEffect(() => {
    if (!token) return;
    api
      .getSubmission(token, code)
      .then(setSubmission)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load submission"));
  }, [token, code]);

  async function handleDownload() {
    if (!token) return;
    setDownloading(true);
    try {
      const blob = await api.downloadReport(token, code);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${code}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Report not available yet");
    } finally {
      setDownloading(false);
    }
  }

  if (error) return <div className="alert alert-error">{error}</div>;
  if (!submission) return <p className="spinner-text">Loading…</p>;

  return (
    <>
      <div className="page-header flex-row">
        <div>
          <h1>{submission.submission_code}</h1>
          <p>Created {new Date(submission.created_at).toLocaleString()}</p>
        </div>
        {submission.status === "published" && (
          <button className="btn" onClick={handleDownload} disabled={downloading}>
            {downloading ? "Downloading…" : "Download report"}
          </button>
        )}
      </div>
      <SubmissionOverview submission={submission} />
    </>
  );
}

export default function SubmissionDetailClient({ code }: { code: string }) {
  return (
    <RequireAuth>
      <Detail code={code} />
    </RequireAuth>
  );
}
