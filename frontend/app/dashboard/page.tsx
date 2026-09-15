"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Card, buttonVariants, cn } from "@heroui/react";
import RequireAuth from "@/components/RequireAuth";
import StatusBadge from "@/components/StatusBadge";
import Skeleton from "@/components/Skeleton";
import EmptyState from "@/components/EmptyState";
import ErrorState from "@/components/ErrorState";
import { useAuth } from "@/lib/auth-context";
import { CATEGORY_ORDER, gradeTierClass } from "@/lib/grade-display";
import { useLocale, useTranslations } from "@/lib/i18n/context";
import * as api from "@/lib/api";

/** The four combined scores, compact. A null is "not measurable" and reads
 *  as a dash -- never a zero. The full category name is for screen readers;
 *  the abbreviation is what fits beside it. */
function ScoreStrip({ scores }: { scores: api.SubmissionSummary["scores"] }) {
  const t = useTranslations();
  const present = CATEGORY_ORDER.filter((c) => c in scores);
  if (present.length === 0) return null;
  return (
    <div className="flex flex-wrap gap-1.5">
      {present.map((category) => {
        const value = scores[category] ?? null;
        return (
          <span
            key={category}
            className={`inline-flex items-baseline gap-1 rounded-md px-1.5 py-0.5 text-xs ${
              value === null ? "text-muted" : gradeTierClass(value)
            }`}
          >
            <span aria-hidden="true" className="opacity-80">
              {t.dashboard.scoreAbbrev[category]}
            </span>
            <span className="sr-only">{t.category[category]}</span>
            <span className="font-semibold tabular-nums">{value === null ? "—" : value.toFixed(1)}</span>
          </span>
        );
      })}
    </div>
  );
}

function DashboardList() {
  const { token } = useAuth();
  const { locale } = useLocale();
  const t = useTranslations();
  const [submissions, setSubmissions] = useState<api.SubmissionSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    if (!token) return;
    setError(null);
    api
      .listSubmissions(token)
      .then(setSubmissions)
      .catch((err) => setError(err instanceof Error ? err.message : t.dashboard.loadFailed));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  // eslint-disable-next-line react-hooks/set-state-in-effect -- load() only clears the error and starts a fetch; deps are stable, so this runs once per token change
  useEffect(load, [load]);

  return (
    <>
      <div className="mb-5 flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-foreground">{t.dashboard.title}</h1>
          <p className="text-sm text-muted">{t.dashboard.subtitle}</p>
        </div>
        <Link href="/dashboard/new" className={cn(buttonVariants({ variant: "primary" }), "btn-press btn-neon-hover")}>
          {t.dashboard.newSubmission}
        </Link>
      </div>

      {error ? (
        <ErrorState message={error} onRetry={load} retryLabel={t.common.retry} />
      ) : (
        <Card>
          <Card.Content>
            {submissions === null ? (
              <div className="flex flex-col gap-3">
                <Skeleton className="h-12 w-full" />
                <Skeleton className="h-12 w-full" />
                <Skeleton className="h-12 w-full" />
              </div>
            ) : submissions.length === 0 ? (
              <EmptyState
                title={t.dashboard.emptyTitle}
                description={t.dashboard.emptyDescription}
                actionLabel={t.dashboard.emptyCta}
                actionHref="/dashboard/new"
              />
            ) : (
              <ul className="flex flex-col divide-y divide-border">
                {submissions.map((s) => {
                  // An uncharged photo draft: the customer's own unfinished
                  // work, which costs nothing until it is analysed.
                  const draft =
                    !s.charged && !s.mail_in && (s.status === "created" || s.status === "awaiting_scans");
                  return (
                    <li key={s.submission_code}>
                      {/* The whole row is the link: the rows above and below
                          are other cards, so a small target opens the wrong one. */}
                      <Link
                        href={`/dashboard/${s.submission_code}`}
                        className="-mx-2 flex flex-col gap-2 rounded-lg px-2 py-3 hover:bg-surface-secondary sm:flex-row sm:items-center sm:justify-between sm:gap-4"
                      >
                        <div className="min-w-0">
                          <p className="truncate font-semibold text-foreground">
                            {s.card_name ?? t.checkFlow.untitledCard}
                          </p>
                          <p className="text-xs text-muted">
                            {s.game ? `${s.game} · ` : ""}
                            {new Date(s.created_at).toLocaleDateString(locale)}
                            {draft ? ` · ${t.dashboard.notCharged}` : ""}
                          </p>
                        </div>
                        <div className="flex flex-wrap items-center gap-2 sm:justify-end">
                          <ScoreStrip scores={s.scores} />
                          <StatusBadge
                            status={s.status}
                            locale={locale}
                            audience="customer"
                            mailIn={s.mail_in}
                            charged={s.charged}
                          />
                          <span className="text-sm text-accent">{draft ? t.dashboard.continue : t.dashboard.view}</span>
                        </div>
                      </Link>
                    </li>
                  );
                })}
              </ul>
            )}
          </Card.Content>
        </Card>
      )}
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
