"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import RequireAuth from "@/components/RequireAuth";
import StatusBadge from "@/components/StatusBadge";
import { useAuth } from "@/lib/auth-context";
import * as api from "@/lib/api";

function DashboardList() {
  const { token } = useAuth();
  const [submissions, setSubmissions] = useState<api.SubmissionSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) return;
    api
      .listSubmissions(token)
      .then(setSubmissions)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load submissions"));
  }, [token]);

  return (
    <>
      <div className="page-header flex-row">
        <div>
          <h1>Your submissions</h1>
          <p>Track every card you&apos;ve sent in for pre-grading.</p>
        </div>
        <Link href="/dashboard/new" className="btn">
          New submission
        </Link>
      </div>
      {error && <div className="alert alert-error">{error}</div>}
      <div className="card">
        {submissions === null ? (
          <p className="spinner-text">Loading…</p>
        ) : submissions.length === 0 ? (
          <p className="muted">
            No submissions yet. <Link href="/dashboard/new">Create your first one.</Link>
          </p>
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
                    <Link href={`/dashboard/${s.submission_code}`}>View</Link>
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

export default function DashboardPage() {
  return (
    <RequireAuth>
      <DashboardList />
    </RequireAuth>
  );
}
