"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Card } from "@heroui/react";
import Button from "@/components/Button";
import ConfirmDialog from "@/components/ConfirmDialog";
import RequireAuth from "@/components/RequireAuth";
import SubmissionOverview from "@/components/SubmissionOverview";
import Skeleton from "@/components/Skeleton";
import ErrorState from "@/components/ErrorState";
import ProcessingState from "@/components/ProcessingState";
import UploadStep from "@/components/UploadStep";
import { useAuth } from "@/lib/auth-context";
import { toastError } from "@/lib/toast";
import { useLocale, useTranslations } from "@/lib/i18n/context";
import * as api from "@/lib/api";

const PENDING_STATUSES = new Set(["created", "awaiting_scans", "processing"]);
// Mirrors the backend's upload gate (created/awaiting_scans/draft_ready) --
// once a submission is approved/published/errored, scans can no longer be
// added.
const UPLOAD_ALLOWED_STATUSES = new Set(["created", "awaiting_scans", "draft_ready"]);

function Detail({ code }: { code: string }) {
  const { token } = useAuth();
  const { locale } = useLocale();
  const t = useTranslations();
  const router = useRouter();
  const [submission, setSubmission] = useState<api.SubmissionDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [downloading, setDownloading] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const load = useCallback(() => {
    if (!token) return;
    setError(null);
    api
      .getSubmission(token, code)
      .then(setSubmission)
      .catch((err) => setError(err instanceof Error ? err.message : t.submissionDetail.loadFailed));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, code]);

  useEffect(load, [load]);

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
      toastError(err instanceof Error ? err.message : t.submissionDetail.downloadFailed);
    } finally {
      setDownloading(false);
    }
  }

  async function handleDelete() {
    if (!token) return;
    setDeleting(true);
    try {
      await api.deleteSubmission(token, code);
      router.push("/dashboard");
    } catch (err) {
      toastError(err instanceof Error ? err.message : t.submissionDetail.deleteFailed);
      setDeleting(false);
      setConfirmDelete(false);
    }
  }

  async function handleToggleRegion(regionKey: string, dismissed: boolean) {
    if (!token) return;
    try {
      setSubmission(await api.toggleRegion(token, code, regionKey, dismissed));
    } catch (err) {
      toastError(err instanceof Error ? err.message : t.breakout.toggleFailed);
    }
  }

  if (error) {
    return <ErrorState message={error} onRetry={load} retryLabel={t.common.retry} />;
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
          <p className="text-sm text-muted">
            {t.submissionDetail.createdOn} {new Date(submission.created_at).toLocaleString()}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {submission.status === "published" && (
            <Button variant="primary" onPress={handleDownload} isDisabled={downloading}>
              {downloading ? t.submissionDetail.downloading : t.submissionDetail.download}
            </Button>
          )}
          <Button variant="outline" onPress={() => setConfirmDelete(true)}>
            {t.submissionDetail.deleteButton}
          </Button>
        </div>
      </div>
      <ConfirmDialog
        open={confirmDelete}
        title={t.submissionDetail.deleteTitle}
        body={t.submissionDetail.deleteBody}
        confirmLabel={t.submissionDetail.deleteConfirm}
        cancelLabel={t.submissionDetail.deleteCancel}
        destructive
        busy={deleting}
        onConfirm={handleDelete}
        onCancel={() => setConfirmDelete(false)}
      />
      {PENDING_STATUSES.has(submission.status) && !submission.confirmed_sides.includes("front") ? (
        <UploadStep
          code={code}
          token={token!}
          scanSides={submission.scan_sides}
          confirmedSides={submission.confirmed_sides}
          onUploaded={setSubmission}
        />
      ) : PENDING_STATUSES.has(submission.status) ? (
        <ProcessingState status={submission.status} locale={locale} />
      ) : (
        <div className="flex flex-col gap-5">
          <SubmissionOverview
            submission={submission}
            token={token!}
            locale={locale}
            onToggleRegion={handleToggleRegion}
          />
          {UPLOAD_ALLOWED_STATUSES.has(submission.status) && !submission.confirmed_sides.includes("back") && (
            <UploadStep
              code={code}
              token={token!}
              scanSides={submission.scan_sides}
              confirmedSides={submission.confirmed_sides}
              onUploaded={setSubmission}
            />
          )}
        </div>
      )}
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
