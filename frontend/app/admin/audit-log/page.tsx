"use client";

import { useEffect, useState } from "react";
import RequireAuth from "@/components/RequireAuth";
import { useAuth } from "@/lib/auth-context";
import * as api from "@/lib/api";

const PAGE_SIZE = 50;

function AuditLogList() {
  const { token } = useAuth();
  const [entries, setEntries] = useState<api.AuditLogEntry[] | null>(null);
  const [offset, setOffset] = useState(0);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) return;
    api
      .getAuditLog(token, { limit: PAGE_SIZE, offset })
      .then(setEntries)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load audit log"));
  }, [token, offset]);

  return (
    <>
      <div className="page-header">
        <h1>Audit log</h1>
        <p>Approvals, publish events, and auto-publish overrides, most recent first.</p>
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      <div className="card">
        {entries === null ? (
          <p className="spinner-text">Loading…</p>
        ) : entries.length === 0 ? (
          <p className="muted">Nothing here yet.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>When</th>
                <th>Action</th>
                <th>Submission</th>
                <th>Actor</th>
                <th>Detail</th>
              </tr>
            </thead>
            <tbody>
              {entries.map((entry) => (
                <tr key={entry.id}>
                  <td style={{ whiteSpace: "nowrap" }}>{new Date(entry.created_at).toLocaleString()}</td>
                  <td>{entry.action}</td>
                  <td>{entry.submission_code ?? "—"}</td>
                  <td>{entry.user_email ?? <span className="muted">system</span>}</td>
                  <td style={{ fontSize: "0.82rem", color: "var(--muted)" }}>
                    {Object.keys(entry.detail).length > 0 ? JSON.stringify(entry.detail) : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="flex-row" style={{ marginTop: 12 }}>
        <button
          className="btn btn-secondary btn-sm"
          onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
          disabled={offset === 0}
        >
          Newer
        </button>
        <button
          className="btn btn-secondary btn-sm"
          onClick={() => setOffset(offset + PAGE_SIZE)}
          disabled={!entries || entries.length < PAGE_SIZE}
        >
          Older
        </button>
      </div>
    </>
  );
}

export default function AuditLogPage() {
  return (
    <RequireAuth role="operator">
      <AuditLogList />
    </RequireAuth>
  );
}
