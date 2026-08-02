"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Chip } from "@heroui/react";
import { useQuota } from "@/lib/quota-context";
import { useTranslations } from "@/lib/i18n/context";

/**
 * Formats the gap to `iso` as a coarse countdown: days and hours, or hours and
 * minutes inside a day.
 *
 * Deliberately not second-by-second. The reset is up to a week away, so a
 * ticking seconds display would be noise that also forces a re-render every
 * second on every page.
 */
function formatRemaining(iso: string, now: number, labels: { d: string; h: string; m: string }): string | null {
  const ms = new Date(iso).getTime() - now;
  if (!Number.isFinite(ms) || ms <= 0) return null;

  const minutes = Math.floor(ms / 60000);
  const hours = Math.floor(minutes / 60);
  const days = Math.floor(hours / 24);

  if (days >= 1) return `${days}${labels.d} ${hours % 24}${labels.h}`;
  if (hours >= 1) return `${hours}${labels.h} ${minutes % 60}${labels.m}`;
  return `${Math.max(1, minutes)}${labels.m}`;
}

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
    <Link href="/services" aria-label={t.quota.ariaLabel} className="shrink-0">
      <Chip size="sm" variant="soft" color={exhausted ? "danger" : "success"}>
        {label}
      </Chip>
    </Link>
  );
}
