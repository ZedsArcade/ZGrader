"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Chip } from "@heroui/react";
import { useQuota } from "@/lib/quota-context";
import { useTranslations } from "@/lib/i18n/context";
import { formatRemaining } from "@/lib/countdown";

export default function QuotaChip() {
  const { quota } = useQuota();
  const t = useTranslations();
  const [now, setNow] = useState(() => Date.now());

  // A minute is fine given the display granularity above, and keeps this off
  // the render path the rest of the time.
  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), 60_000);
    return () => window.clearInterval(id);
  }, []);

  // Unknown (signed out, loading, or a failed fetch) shows nothing rather
  // than a zero -- telling someone they are out of checks because a request
  // failed would be worse than saying nothing.
  if (!quota) return null;
  // An unlimited plan gets no counter at all. A subscriber does not need to
  // think about credits, and an infinity symbol invites the question.
  if (quota.unlimited) return null;

  const remaining = quota.remaining ?? 0;
  const exhausted = remaining === 0;
  const countdown = quota.resets_at
    ? formatRemaining(quota.resets_at, now, {
        d: t.quota.unitDay,
        h: t.quota.unitHour,
        m: t.quota.unitMinute,
      })
    : null;

  const label = exhausted
    ? countdown
      ? t.quota.chipExhaustedIn.replace("{time}", countdown)
      : t.quota.chipExhausted
    : t.quota.chipRemaining.replace("{n}", String(remaining));

  return (
    <Link href="/pricing" aria-label={t.quota.ariaLabel} className="shrink-0">
      <Chip size="sm" variant="soft" color={exhausted ? "danger" : "success"}>
        {label}
      </Chip>
    </Link>
  );
}
