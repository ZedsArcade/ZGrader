"use client";

import { useEffect, useState } from "react";
import { Button, Card, ListBox, Select, Skeleton } from "@heroui/react";
import RequireAuth from "@/components/RequireAuth";
import SubmissionOverview from "@/components/SubmissionOverview";
import { useAuth } from "@/lib/auth-context";
import { toastError, toastSuccess } from "@/lib/toast";
import * as api from "@/lib/api";

const AUTO_PUBLISH_OPTIONS: { label: string; value: string }[] = [
  { label: "Inherit global default", value: "inherit" },
  { label: "Force on for this submission", value: "on" },
  { label: "Force off for this submission", value: "off" },
];

function autoPublishToOption(value: boolean | null): string {
  if (value === null) return "inherit";
  return value ? "on" : "off";
}

function optionToAutoPublish(option: string): boolean | null {
  if (option === "on") return true;
  if (option === "off") return false;
  return null;
}

function AdminDetail({ code }: { code: string }) {
  const { token } = useAuth();
  const [submission, setSubmission] = useState<api.SubmissionDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  function load() {
    if (!token) return;
    api
      .getSubmission(token, code)
      .then(setSubmission)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load submission"));
  }

  useEffect(load, [token, code]);

  async function handleApprove() {
    if (!token) return;
    setBusy(true);
    try {
      const updated = await api.approveSubmission(token, code);
      setSubmission(updated);
      toastSuccess("Approved and published.");
    } catch (err) {
      toastError(err instanceof Error ? err.message : "Approve failed");
    } finally {
      setBusy(false);
    }
  }

  async function handleAutoPublishChange(option: string) {
    if (!token) return;
    setBusy(true);
    try {
      const updated = await api.setAutoPublish(token, code, optionToAutoPublish(option));
      setSubmission(updated);
    } catch (err) {
      toastError(err instanceof Error ? err.message : "Failed to update auto-publish");
    } finally {
      setBusy(false);
    }
  }

  if (error && !submission) {
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
      <div className="mb-5">
        <h1 className="text-2xl font-bold text-foreground">{submission.submission_code}</h1>
        <p className="text-sm text-muted">Created {new Date(submission.created_at).toLocaleString()}</p>
      </div>

      <Card>
        <Card.Content>
          <div className="flex items-center justify-between gap-4">
            <div>
              <h3 className="text-sm font-semibold text-foreground">Auto-publish</h3>
              <p className="mt-1 text-sm text-muted">
                Controls whether this submission publishes automatically once analysis finishes,
                or waits for manual approval below.
              </p>
            </div>
            <Select.Root
              selectedKey={autoPublishToOption(submission.auto_publish)}
              onSelectionChange={(key) => handleAutoPublishChange(String(key))}
              isDisabled={busy}
            >
              <Select.Trigger>
                <Select.Value />
                <Select.Indicator />
              </Select.Trigger>
              <Select.Popover>
                <ListBox>
                  {AUTO_PUBLISH_OPTIONS.map((opt) => (
                    <ListBox.Item id={opt.value} key={opt.value} textValue={opt.label}>
                      {opt.label}
                    </ListBox.Item>
                  ))}
                </ListBox>
              </Select.Popover>
            </Select.Root>
          </div>

          {submission.status === "draft_ready" && (
            <div className="mt-5">
              <Button variant="primary" onPress={handleApprove} isDisabled={busy}>
                {busy ? "Working…" : "Approve & publish"}
              </Button>
            </div>
          )}
        </Card.Content>
      </Card>

      <div className="mt-5">
        <SubmissionOverview submission={submission} />
      </div>
    </>
  );
}

export default function AdminDetailClient({ code }: { code: string }) {
  return (
    <RequireAuth role="operator">
      <AdminDetail code={code} />
    </RequireAuth>
  );
}
