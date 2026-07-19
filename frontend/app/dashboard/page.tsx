"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Card, Skeleton, Table, buttonVariants } from "@heroui/react";
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
      <div className="mb-5 flex items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Your submissions</h1>
          <p className="text-sm text-muted">Track every card you&apos;ve sent in for pre-grading.</p>
        </div>
        <Link href="/dashboard/new" className={buttonVariants({ variant: "primary" })}>
          New submission
        </Link>
      </div>

      {error && (
        <Card className="mb-5">
          <Card.Content>
            <p className="text-sm text-danger">{error}</p>
          </Card.Content>
        </Card>
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
            <p className="text-sm text-muted">
              No submissions yet.{" "}
              <Link href="/dashboard/new" className="text-accent hover:underline">
                Create your first one.
              </Link>
            </p>
          ) : (
            <Table>
              <Table.ScrollContainer>
                <Table.Content aria-label="Your submissions">
                  <Table.Header>
                    <Table.Column isRowHeader>Code</Table.Column>
                    <Table.Column>Status</Table.Column>
                    <Table.Column>Created</Table.Column>
                    <Table.Column>{""}</Table.Column>
                  </Table.Header>
                  <Table.Body>
                    {submissions.map((s) => (
                      <Table.Row key={s.submission_code} id={s.submission_code}>
                        <Table.Cell>{s.submission_code}</Table.Cell>
                        <Table.Cell>
                          <StatusBadge status={s.status} />
                        </Table.Cell>
                        <Table.Cell>{new Date(s.created_at).toLocaleDateString()}</Table.Cell>
                        <Table.Cell>
                          <Link href={`/dashboard/${s.submission_code}`} className="text-accent hover:underline">
                            View
                          </Link>
                        </Table.Cell>
                      </Table.Row>
                    ))}
                  </Table.Body>
                </Table.Content>
              </Table.ScrollContainer>
            </Table>
          )}
        </Card.Content>
      </Card>
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
