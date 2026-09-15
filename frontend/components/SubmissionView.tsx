"use client";

import { useCallback, useEffect, useState, type ReactNode } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Card, buttonVariants, cn } from "@heroui/react";
import Button from "@/components/Button";
import CardLabelFields, { labelChanges, labelsOf, type CardLabels } from "@/components/CardLabelFields";
import CheckFlow from "@/components/CheckFlow";
import ConfirmDialog from "@/components/ConfirmDialog";
import ErrorState from "@/components/ErrorState";
import ProcessingState from "@/components/ProcessingState";
import SharePanel from "@/components/SharePanel";
import Skeleton from "@/components/Skeleton";
import StatusBadge from "@/components/StatusBadge";
import SubmissionOverview from "@/components/SubmissionOverview";
import UploadStep from "@/components/UploadStep";
import { useAuth } from "@/lib/auth-context";
import { useLocale, useTranslations } from "@/lib/i18n/context";
import { toastError, toastSuccess } from "@/lib/toast";
import { useSubmissionPoll } from "@/lib/use-submission-poll";
import * as api from "@/lib/api";

const PRE_ANALYSIS = new Set<api.SubmissionStatus>(["created", "awaiting_scans"]);
// Mirrors the backend's upload gate: once approved/published/errored, no
// more scans.
const UPLOAD_ALLOWED = new Set<api.SubmissionStatus>(["created", "awaiting_scans", "draft_ready"]);
const IN_REVIEW = new Set<api.SubmissionStatus>(["draft_ready", "approved"]);

function SubmissionHeader({
  submission,
  onChange,
  actions,
}: {
  submission: api.SubmissionDetail;
  onChange: (next: api.SubmissionDetail) => void;
  actions: ReactNode;
}) {
  const { token } = useAuth();
  const { locale } = useLocale();
  const t = useTranslations();
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [labels, setLabels] = useState<CardLabels>(() => labelsOf(submission.card));
  const name = submission.card?.card_name ?? null;

  async function save() {
    if (!token) return;
    const changes = labelChanges(labelsOf(submission.card), labels);
    if (Object.keys(changes).length === 0) {
      setEditing(false);
      return;
    }
    setSaving(true);
    try {
      onChange(await api.updateCard(token, submission.submission_code, changes));
      setEditing(false);
      toastSuccess(t.checkFlow.detailsSaved);
    } catch (err) {
      toastError(err instanceof api.ApiError ? err.message : t.checkFlow.detailsFailed);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="mb-5 flex flex-col gap-3">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <h1 className="break-words text-2xl font-bold text-foreground">{name ?? t.checkFlow.untitledCard}</h1>
          {/* The code is for support emails, not the headline: it is
              sequential and means nothing to the customer. */}
          <p className="text-xs text-muted">
            {t.checkFlow.refLabel.replace("{code}", submission.submission_code)} ·{" "}
            {new Date(submission.created_at).toLocaleDateString(locale)}
            {!editing && (
              <button
                type="button"
                onClick={() => {
                  setLabels(labelsOf(submission.card));
                  setEditing(true);
                }}
                className="-my-2 ml-2 inline-flex py-2 text-accent hover:underline"
              >
                {name ? t.checkFlow.editDetails : t.checkFlow.addName}
              </button>
            )}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <StatusBadge
            status={submission.status}
            locale={locale}
            audience="customer"
            mailIn={submission.mail_in}
            charged={submission.charged}
          />
          {actions}
        </div>
      </div>
      {editing && (
        <Card>
          <Card.Content className="flex flex-col gap-3">
            <CardLabelFields value={labels} onChange={setLabels} />
            <div className="flex flex-wrap gap-2">
              <Button variant="primary" size="sm" onPress={save} isDisabled={saving}>
                {t.checkFlow.saveDetails}
              </Button>
              <Button variant="outline" size="sm" onPress={() => setEditing(false)}>
                {t.checkFlow.cancelEdit}
              </Button>
            </div>
          </Card.Content>
        </Card>
      )}
    </div>
  );
}

function Notice({ title, body }: { title: string; body: string }) {
  return (
    <Card>
      <Card.Content>
        <p className="text-sm font-semibold text-foreground">{title}</p>
        <p className="mt-1 text-sm text-muted">{body}</p>
      </Card.Content>
    </Card>
  );
}

function AnalysisFailed({ charged, onDelete }: { charged: boolean; onDelete: () => void }) {
  const t = useTranslations();
  return (
    <Card>
      <Card.Header>
        <Card.Title>{t.checkFlow.errorTitle}</Card.Title>
        {/* A charged submission errored on a re-analysis after one that
            scored, so "it didn't use a check" would be untrue. */}
        {!charged && <Card.Description>{t.checkFlow.errorFree}</Card.Description>}
      </Card.Header>
      <Card.Content className="flex flex-col gap-4">
        <p className="text-sm text-muted">{t.checkFlow.errorTips}</p>
        <div className="flex flex-wrap gap-2">
          <Link href="/dashboard/new" className={cn(buttonVariants({ variant: "primary" }), "btn-press btn-neon-hover")}>
            {t.checkFlow.tryAnother}
          </Link>
          <Button variant="outline" onPress={onDelete}>
            {t.submissionDetail.deleteButton}
          </Button>
        </div>
      </Card.Content>
    </Card>
  );
}

/**
 * Every state of one submission, from "no photo yet" to the published report.
 * Rendered by /dashboard/new (code null) and /dashboard/[code]. It owns the
 * submission state, so the draft CheckFlow creates on the first page becomes
 * the report on the same page without a navigation.
 */
export default function SubmissionView({ code }: { code: string | null }) {
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
    if (!token || !code) return;
    setError(null);
    api
      .getSubmission(token, code)
      .then(setSubmission)
      .catch((err) => setError(err instanceof Error ? err.message : t.submissionDetail.loadFailed));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, code]);

  // load clears the error synchronously before its async request -- exactly
  // the "reset state, then reload" shape this rule exists to flag in
  // general, and exactly what this effect is for.
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(load, [load]);

  const analysing =
    submission !== null &&
    (submission.status === "processing" ||
      (PRE_ANALYSIS.has(submission.status) && submission.confirmed_sides.includes("front")));

  const pollTimedOut = useSubmissionPoll(analysing, async () => {
    if (!token || !submission) return;
    setSubmission(await api.getSubmission(token, submission.submission_code));
  });

  async function handleDownload() {
    if (!token || !submission) return;
    setDownloading(true);
    try {
      const blob = await api.downloadReport(token, submission.submission_code);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${submission.submission_code}.pdf`;
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
    if (!token || !submission) return;
    setDeleting(true);
    try {
      await api.deleteSubmission(token, submission.submission_code);
      router.push("/dashboard");
    } catch (err) {
      toastError(err instanceof Error ? err.message : t.submissionDetail.deleteFailed);
      setDeleting(false);
      setConfirmDelete(false);
    }
  }

  async function handleToggleRegion(regionKey: string, dismissed: boolean) {
    if (!token || !submission) return;
    try {
      setSubmission(await api.toggleRegion(token, submission.submission_code, regionKey, dismissed));
    } catch (err) {
      toastError(err instanceof Error ? err.message : t.breakout.toggleFailed);
    }
  }

  if (error) return <ErrorState message={error} onRetry={load} retryLabel={t.common.retry} />;
  if (code && !submission) {
    return (
      <div className="flex flex-col gap-5">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-64 w-full rounded-xl" />
      </div>
    );
  }
  if (!submission) return <CheckFlow submission={null} onChange={setSubmission} />;

  const s = submission;
  let body: ReactNode;
  if (s.mail_in && PRE_ANALYSIS.has(s.status) && !analysing) {
    body = (
      <Notice
        title={t.checkFlow.awaitingCardTitle}
        body={t.checkFlow.awaitingCardBody.replace("{code}", s.submission_code)}
      />
    );
  } else if (PRE_ANALYSIS.has(s.status) && !s.confirmed_sides.includes("front")) {
    body = <CheckFlow submission={s} onChange={setSubmission} />;
  } else if (analysing) {
    body = <ProcessingState status="processing" locale={locale} stillWorking={pollTimedOut} />;
  } else if (s.status === "error") {
    body = <AnalysisFailed charged={s.charged} onDelete={() => setConfirmDelete(true)} />;
  } else {
    body = (
      <div className="flex flex-col gap-5">
        {IN_REVIEW.has(s.status) && <Notice title={t.checkFlow.reviewTitle} body={t.checkFlow.reviewBody} />}
        <SubmissionOverview
          submission={s}
          token={token!}
          locale={locale}
          audience="customer"
          onToggleRegion={handleToggleRegion}
          onAdjusted={setSubmission}
          afterScores={
            UPLOAD_ALLOWED.has(s.status) && !s.confirmed_sides.includes("back") ? (
              <UploadStep code={s.submission_code} token={token!} scanSides={s.scan_sides} onUploaded={setSubmission} />
            ) : null
          }
        />
        <SharePanel code={s.submission_code} token={token!} publishable={s.status === "published"} />
      </div>
    );
  }

  return (
    <>
      <SubmissionHeader
        submission={s}
        onChange={setSubmission}
        actions={
          <>
            {s.status === "published" && (
              <Button variant="primary" onPress={handleDownload} isDisabled={downloading}>
                {downloading ? t.submissionDetail.downloading : t.submissionDetail.download}
              </Button>
            )}
            <Button variant="outline" onPress={() => setConfirmDelete(true)}>
              {t.submissionDetail.deleteButton}
            </Button>
          </>
        }
      />
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
      {body}
    </>
  );
}
