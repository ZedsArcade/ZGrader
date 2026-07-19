"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Card, Input, Skeleton, Table, TextField, buttonVariants } from "@heroui/react";
import type { SortDescriptor } from "react-aria-components";
import RequireAuth from "@/components/RequireAuth";
import StatusBadge from "@/components/StatusBadge";
import { useAuth } from "@/lib/auth-context";
import * as api from "@/lib/api";

function AdminOverview() {
  const { token } = useAuth();
  const [submissions, setSubmissions] = useState<api.SubmissionSummary[] | null>(null);
  const [stats, setStats] = useState<api.Stats | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState("");
  const [sortDescriptor, setSortDescriptor] = useState<SortDescriptor>({
    column: "created_at",
    direction: "descending",
  });

  useEffect(() => {
    if (!token) return;
    Promise.all([api.listSubmissions(token), api.getStats(token)])
      .then(([subs, s]) => {
        setSubmissions(subs);
        setStats(s);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load admin data"));
  }, [token]);

  const visibleSubmissions = useMemo(() => {
    if (!submissions) return [];
    const needle = filter.trim().toLowerCase();
    const filtered = needle
      ? submissions.filter(
          (s) =>
            s.submission_code.toLowerCase().includes(needle) || s.status.toLowerCase().includes(needle)
        )
      : submissions;
    const column = sortDescriptor.column === "status" ? "status" : "created_at";
    const sorted = [...filtered].sort((a, b) => {
      const cmp = column === "status" ? a.status.localeCompare(b.status) : a.created_at.localeCompare(b.created_at);
      return sortDescriptor.direction === "descending" ? -cmp : cmp;
    });
    return sorted;
  }, [submissions, filter, sortDescriptor]);

  return (
    <>
      <div className="mb-5 flex items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Admin</h1>
          <p className="text-sm text-muted">All client submissions, business-wide.</p>
        </div>
        <div className="flex gap-2">
          <Link href="/admin/audit-log" className={buttonVariants({ variant: "outline" })}>
            Audit log
          </Link>
          <Link href="/admin/settings" className={buttonVariants({ variant: "outline" })}>
            Settings
          </Link>
        </div>
      </div>

      {error && (
        <Card className="mb-5">
          <Card.Content>
            <p className="text-sm text-danger">{error}</p>
          </Card.Content>
        </Card>
      )}

      {stats && (
        <div className="mb-5 grid grid-cols-1 gap-3 sm:grid-cols-3">
          <div className="rounded-xl border border-border bg-surface-secondary p-3">
            <div className="text-xs text-muted">Total submissions</div>
            <div className="mt-1 text-2xl font-semibold text-foreground">{stats.total_submissions}</div>
          </div>
          <div className="rounded-xl border border-border bg-surface-secondary p-3">
            <div className="text-xs text-muted">Draft ready</div>
            <div className="mt-1 text-2xl font-semibold text-foreground">
              {stats.by_status.draft_ready ?? 0}
            </div>
          </div>
          <div className="rounded-xl border border-border bg-surface-secondary p-3">
            <div className="text-xs text-muted">Published reports</div>
            <div className="mt-1 text-2xl font-semibold text-foreground">{stats.published_reports}</div>
          </div>
        </div>
      )}

      <Card>
        <Card.Content>
          {submissions === null ? (
            <div className="flex flex-col gap-3">
              <Skeleton className="h-9 w-full" />
              <Skeleton className="h-9 w-full" />
              <Skeleton className="h-9 w-full" />
            </div>
          ) : submissions.length === 0 ? (
            <p className="text-sm text-muted">No submissions yet.</p>
          ) : (
            <>
              <TextField
                aria-label="Filter submissions"
                value={filter}
                onChange={setFilter}
                fullWidth
                className="mb-4"
              >
                <Input placeholder="Filter by code or status" />
              </TextField>
              <Table>
                <Table.ScrollContainer>
                  <Table.Content aria-label="All submissions" sortDescriptor={sortDescriptor} onSortChange={setSortDescriptor}>
                    <Table.Header>
                      <Table.Column isRowHeader>Code</Table.Column>
                      <Table.Column id="status" allowsSorting>
                        {({ sortDirection }) => (
                          <Table.SortableColumnHeader sortDirection={sortDirection}>Status</Table.SortableColumnHeader>
                        )}
                      </Table.Column>
                      <Table.Column id="created_at" allowsSorting>
                        {({ sortDirection }) => (
                          <Table.SortableColumnHeader sortDirection={sortDirection}>Created</Table.SortableColumnHeader>
                        )}
                      </Table.Column>
                      <Table.Column>{""}</Table.Column>
                    </Table.Header>
                    <Table.Body>
                      {visibleSubmissions.map((s) => (
                        <Table.Row key={s.submission_code} id={s.submission_code}>
                          <Table.Cell>{s.submission_code}</Table.Cell>
                          <Table.Cell>
                            <StatusBadge status={s.status} />
                          </Table.Cell>
                          <Table.Cell>{new Date(s.created_at).toLocaleDateString()}</Table.Cell>
                          <Table.Cell>
                            <Link href={`/admin/${s.submission_code}`} className="text-accent hover:underline">
                              Review
                            </Link>
                          </Table.Cell>
                        </Table.Row>
                      ))}
                    </Table.Body>
                  </Table.Content>
                </Table.ScrollContainer>
              </Table>
            </>
          )}
        </Card.Content>
      </Card>
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
