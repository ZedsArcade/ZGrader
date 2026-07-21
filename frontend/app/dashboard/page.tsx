"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Card, Skeleton, Table, buttonVariants } from "@heroui/react";
import RequireAuth from "@/components/RequireAuth";
import StatusBadge from "@/components/StatusBadge";
import { useAuth } from "@/lib/auth-context";
import { useLocale, useTranslations } from "@/lib/i18n/context";
import * as api from "@/lib/api";

function DashboardList() {
  const { token } = useAuth();
  const { locale } = useLocale();
  const t = useTranslations();
  const [submissions, setSubmissions] = useState<api.SubmissionSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) return;
    api
      .listSubmissions(token)
      .then(setSubmissions)
      .catch((err) => setError(err instanceof Error ? err.message : t.dashboard.loadFailed));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  return (
    <>
      <div className="mb-5 flex items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-foreground">{t.dashboard.title}</h1>
          <p className="text-sm text-muted">{t.dashboard.subtitle}</p>
        </div>
        <Link href="/dashboard/new" className={buttonVariants({ variant: "primary" })}>
          {t.dashboard.newSubmission}
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
              {t.dashboard.empty}{" "}
              <Link href="/dashboard/new" className="text-accent hover:underline">
                {t.dashboard.emptyCta}
              </Link>
            </p>
          ) : (
            <Table>
              <Table.ScrollContainer>
                <Table.Content aria-label={t.dashboard.title}>
                  <Table.Header>
                    <Table.Column isRowHeader>{t.dashboard.colCode}</Table.Column>
                    <Table.Column>{t.dashboard.colStatus}</Table.Column>
                    <Table.Column>{t.dashboard.colCreated}</Table.Column>
                    <Table.Column>{""}</Table.Column>
                  </Table.Header>
                  <Table.Body>
                    {submissions.map((s) => (
                      <Table.Row key={s.submission_code} id={s.submission_code}>
                        <Table.Cell>{s.submission_code}</Table.Cell>
                        <Table.Cell>
                          <StatusBadge status={s.status} locale={locale} />
                        </Table.Cell>
                        <Table.Cell>{new Date(s.created_at).toLocaleDateString()}</Table.Cell>
                        <Table.Cell>
                          <Link href={`/dashboard/${s.submission_code}`} className="text-accent hover:underline">
                            {t.dashboard.view}
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
