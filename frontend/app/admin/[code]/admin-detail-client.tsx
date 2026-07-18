"use client";

import { useEffect, useState } from "react";
import RequireAuth from "@/components/RequireAuth";
import SubmissionOverview from "@/components/SubmissionOverview";
import { useAuth } from "@/lib/auth-context";
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
  const [message, setMessage] = useState<string | null>(null);
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
    setError(null);
    setMessage(null);
    try {
      const updated = await api.approveSubmission(token, code);
      setSubmission(updated);
      setMessage("Approved and published.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Approve failed");
    } finally {
      setBusy(false);
    }
  }

  async function handleAutoPublishChange(option: string) {
    if (!token) return;
    setBusy(true);
    setError(null);
    try {
      const updated = await api.setAutoPublish(token, code, optionToAutoPublish(option));
      setSubmission(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update auto-publish");
    } finally {
      setBusy(false);
    }
  }

  if (error && !submission) return <div className="alert alert-error">{error}</div>;
  if (!submission) return <p className="spinner-text">Loading…</p>;

  return (
    <>
      <div className="page-header">
        <h1>{submission.submission_code}</h1>
        <p>Created {new Date(submission.created_at).toLocaleString()}</p>
      </div>

      {error && <div className="alert alert-error">{error}</div>}
      {message && <div className="alert alert-success">{message}</div>}

      <div className="card">
        <div className="flex-row">
          <div>
            <h3>Auto-publish</h3>
            <p className="muted" style={{ fontSize: "0.85rem" }}>
              Controls whether this submission publishes automatically once analysis finishes,
              or waits for manual approval below.
            </p>
          </div>
          <select
            value={autoPublishToOption(submission.auto_publish)}
            onChange={(e) => handleAutoPublishChange(e.target.value)}
            disabled={busy}
            style={{ width: "auto" }}
          >
            {AUTO_PUBLISH_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>

        {submission.status === "draft_ready" && (
          <div style={{ marginTop: 18 }}>
            <button className="btn" onClick={handleApprove} disabled={busy}>
              {busy ? "Working…" : "Approve & publish"}
            </button>
          </div>
        )}
      </div>

      <SubmissionOverview submission={submission} />
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
