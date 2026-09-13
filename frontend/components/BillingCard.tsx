"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Card } from "@heroui/react";
import Button from "@/components/Button";
import * as api from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { useLocale, useTranslations } from "@/lib/i18n/context";
import { toastError } from "@/lib/toast";
import { useMoney, usePlanName, usePricing } from "@/lib/use-pricing";

/** Mirrors LIVE_STATUSES in backend/zgrader/models/subscription.py. */
const LIVE = new Set(["active", "trialing", "past_due"]);
/** 15 polls at 2s: the "30 seconds" the spec gives the webhook to arrive. */
const POLL_ATTEMPTS = 15;
const POLL_INTERVAL_MS = 2000;

/**
 * The account's subscription, read from our own database -- never inferred
 * from having landed on ?billing=success. Arriving back from Stripe polls
 * until the webhook has recorded the subscription, and if it has not after
 * thirty seconds says so plainly, including that paying again is not the fix.
 *
 * Renders nothing while billing is off: the endpoint answers 404 then.
 */
export default function BillingCard() {
  const { token } = useAuth();
  const t = useTranslations();
  const { locale } = useLocale();
  const money = useMoney();
  const planName = usePlanName();
  const pricing = usePricing();

  const [ready, setReady] = useState(false);
  const [hidden, setHidden] = useState(false);
  const [sub, setSub] = useState<api.BillingSubscription | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [slow, setSlow] = useState(false);
  const [opening, setOpening] = useState(false);
  // Read once, at the first client render -- not inside the effect below.
  // React may run an effect twice (it does in development): the first run
  // strips the query string, its cleanup cancels the poll, and a second run
  // reading the URL again would never know the customer just came back from
  // Stripe. Captured here, both runs agree. Server prerender has no window,
  // which is fine: the card renders nothing until the first fetch anyway.
  const [returning] = useState(
    () =>
      typeof window !== "undefined" &&
      new URLSearchParams(window.location.search).get("billing") === "success"
  );

  useEffect(() => {
    if (!token) return;
    // Strip it so a refresh does not replay the confirming state.
    if (returning && window.location.search) {
      window.history.replaceState(null, "", window.location.pathname);
    }

    let cancelled = false;
    let attempts = 0;
    let timer: ReturnType<typeof setTimeout> | undefined;

    async function poll() {
      try {
        const current = await api.getBillingSubscription(token!);
        if (cancelled) return;
        setSub(current);
        setReady(true);
        if (returning && !(current && LIVE.has(current.status))) {
          attempts += 1;
          if (attempts < POLL_ATTEMPTS) {
            setConfirming(true);
            timer = setTimeout(poll, POLL_INTERVAL_MS);
            return;
          }
          setSlow(true);
        }
        setConfirming(false);
      } catch (err) {
        if (cancelled) return;
        if (err instanceof api.ApiError && err.status === 404) setHidden(true);
        setReady(true);
      }
    }

    void poll();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [token, returning]);

  if (!ready || hidden || !token) return null;

  const formatDate = (iso: string) =>
    // The app's locale, never the browser's -- see frontend/AGENTS.md.
    new Date(iso).toLocaleDateString(locale, { day: "numeric", month: "long", year: "numeric" });
  const billingPeriod = pricing?.plans.find((p) => p.plan === sub?.plan)?.billing_period;
  const periodLabel =
    billingPeriod === "year" ? t.pricing.perYear : billingPeriod === "month" ? t.pricing.perMonth : "";

  async function manage() {
    setOpening(true);
    try {
      const { url } = await api.openBillingPortal(token!);
      window.location.href = url;
    } catch (err) {
      toastError(err instanceof Error ? err.message : t.account.billingFailed);
      setOpening(false);
    }
  }

  const live = sub !== null && LIVE.has(sub.status);

  return (
    <Card>
      <Card.Header>
        <Card.Title>{t.account.billingTitle}</Card.Title>
      </Card.Header>
      <Card.Content className="flex flex-col gap-2">
        {confirming && (
          <p className="text-sm text-muted" aria-live="polite">
            {t.account.billingConfirming}
          </p>
        )}
        {slow && <p className="text-sm text-muted">{t.account.billingSlow}</p>}

        {live ? (
          <>
            <p className="text-sm font-medium text-foreground">
              {t.account.billingPlan
                .replace("{plan}", planName(sub.plan))
                .replace("{price}", sub.amount_pence != null ? money(sub.amount_pence) : "")
                .replace("{period}", periodLabel)}
              {sub.founder && (
                <span className="ml-2 rounded-full border border-border px-2 py-0.5 text-xs text-muted">
                  {t.account.billingFounder}
                </span>
              )}
            </p>
            {sub.cancel_at ? (
              <p className="text-sm text-muted">{t.account.billingEnds.replace("{date}", formatDate(sub.cancel_at))}</p>
            ) : sub.current_period_end ? (
              <p className="text-sm text-muted">
                {t.account.billingRenews.replace("{date}", formatDate(sub.current_period_end))}
              </p>
            ) : null}
            {sub.status === "past_due" && (
              <p className="rounded-lg border border-dashed border-border p-3 text-sm text-foreground">
                {t.account.billingPastDue}
              </p>
            )}
            <div className="mt-2">
              <Button variant="secondary" isDisabled={opening} onPress={manage}>
                {opening ? t.account.billingOpening : t.account.billingManage}
              </Button>
            </div>
          </>
        ) : (
          !confirming && (
            <p className="text-sm text-muted">
              {t.account.billingNone}{" "}
              <Link
                href="/pricing"
                className="-my-2 inline-block py-2 font-semibold text-accent underline-offset-2 hover:underline"
              >
                {t.account.billingSeePlans}
              </Link>
            </p>
          )
        )}
      </Card.Content>
    </Card>
  );
}
