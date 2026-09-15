"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Card, buttonVariants, cn } from "@heroui/react";
import { formatRemaining } from "@/lib/countdown";
import { useTranslations } from "@/lib/i18n/context";
import { useQuota } from "@/lib/quota-context";

/**
 * Shown instead of the photo step when the account has no checks left, so the
 * customer learns it before photographing and cropping rather than after.
 * Links to /pricing, the page that actually sells the plans.
 */
export default function OutOfChecksPanel() {
  const { quota } = useQuota();
  const t = useTranslations();
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), 60_000);
    return () => window.clearInterval(id);
  }, []);

  const countdown = quota?.resets_at
    ? formatRemaining(quota.resets_at, now, {
        d: t.quota.unitDay,
        h: t.quota.unitHour,
        m: t.quota.unitMinute,
      })
    : null;

  return (
    <Card className="mx-auto w-full max-w-2xl">
      <Card.Header>
        <Card.Title>{t.quota.exhaustedTitle}</Card.Title>
      </Card.Header>
      <Card.Content className="flex flex-col gap-4">
        <p className="text-sm text-muted">
          {countdown ? t.quota.exhaustedBody.replace("{time}", countdown) : t.quota.exhaustedBodyNoTimer}
        </p>
        <div>
          <Link href="/pricing" className={cn(buttonVariants({ variant: "primary" }), "btn-press btn-neon-hover")}>
            {t.quota.seePlans}
          </Link>
        </div>
      </Card.Content>
    </Card>
  );
}
