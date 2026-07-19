"use client";

import { useEffect, useState } from "react";
import { Button, Card, Skeleton } from "@heroui/react";
import RequireAuth from "@/components/RequireAuth";
import SubmissionOverview from "@/components/SubmissionOverview";
import { useAuth } from "@/lib/auth-context";
import { toastError } from "@/lib/toast";
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
      toastError(err instanceof Error ? err.message : "Report not available yet");
    } finally {
      setDownloading(false);
    }
  }

  if (error) {
    return (
      <Card>
        <Card.Content>
          <p className="text-sm text-danger">{error}</p>
        </Card.Content>
      </Card>
    );
  }

  if (!submission) {
    return (
      <div className="flex flex-col gap-5">
        <Skeleton className="h-8 w-48" />
        <Card>
          <Card.Content className="flex flex-col gap-4">
            <Skeleton className="h-6 w-64" />
            <Skeleton className="h-24 w-full" />
          </Card.Content>
        </Card>
      </div>
    );
  }

  return (
    <>
      <div className="mb-5 flex items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-foreground">{submission.submission_code}</h1>
          <p className="text-sm text-muted">Created {new Date(submission.created_at).toLocaleString()}</p>
        </div>
        {submission.status === "published" && (
          <Button variant="primary" onPress={handleDownload} isDisabled={downloading}>
            {downloading ? "Downloading…" : "Download report"}
          </Button>
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
