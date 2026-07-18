"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import RequireAuth from "@/components/RequireAuth";
import StatusBadge from "@/components/StatusBadge";
import { useAuth } from "@/lib/auth-context";
import * as api from "@/lib/api";

function AdminOverview() {
  const { token } = useAuth();
  const [submissions, setSubmissions] = useState<api.SubmissionSummary[] | null>(null);
  const [stats, setStats] = useState<api.Stats | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) return;
    Promise.all([api.listSubmissions(token), api.getStats(token)])
      .then(([subs, s]) => {
        setSubmissions(subs);
        setStats(s);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load admin data"));
  }, [token]);

  return (
    <>
      <div className="page-header flex-row">
        <div>
          <h1>Admin</h1>
          <p>All client submissions, business-wide.</p>
        </div>
        <Link href="/admin/settings" className="btn btn-secondary">
          Settings
        </Link>
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      {stats && (
        <div className="score-grid" style={{ marginBottom: 16 }}>
          <div className="score-tile">
            <div className="muted" style={{ fontSize: "0.82rem" }}>
              Total submissions
            </div>
            <div className="value">{stats.total_submissions}</div>
          </div>
          <div className="score-tile">
            <div className="muted" style={{ fontSize: "0.82rem" }}>
              Draft ready
            </div>
            <div className="value">{stats.by_status.draft_ready ?? 0}</div>
          </div>
          <div className="score-tile">
            <div className="muted" style={{ fontSize: "0.82rem" }}>
              Published reports
            </div>
            <div className="value">{stats.published_reports}</div>
          </div>
        </div>
      )}

      <div className="card">
        {submissions === null ? (
          <p className="spinner-text">Loading…</p>
        ) : submissions.length === 0 ? (
          <p className="muted">No submissions yet.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Code</th>
                <th>Status</th>
                <th>Created</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {submissions.map((s) => (
                <tr key={s.submission_code}>
                  <td>{s.submission_code}</td>
                  <td>
                    <StatusBadge status={s.status} />
                  </td>
                  <td>{new Date(s.created_at).toLocaleDateString()}</td>
                  <td>
                    <Link href={`/admin/${s.submission_code}`}>Review</Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}

export default function AdminPage() {
  return (
    <RequireAuth role="operator">
      <AdminOverview />
    </RequireAuth>
  );
}
