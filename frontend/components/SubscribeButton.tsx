"use client";

import Link from "next/link";
import { useState } from "react";
import SubscribeDialog from "@/components/SubscribeDialog";
import type * as api from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { useTranslations } from "@/lib/i18n/context";

const CTA = "inline-flex min-h-11 items-center text-sm font-semibold text-accent link-accent-hover hover:underline";

/**
 * Subscribe, pointed at what the visitor actually needs first. Signed out it
 * is sign-in (no return path yet -- /login has no ?next=); unverified it is
 * the account page, because checkout refuses an unconfirmed address exactly
 * as submitting does.
 */
export default function SubscribeButton({
  plan,
  planName,
  amountPence,
  termsVersion,
}: {
  plan: api.PricedPlan;
  planName: string;
  amountPence: number;
  termsVersion: string;
}) {
  const { user, token } = useAuth();
  const t = useTranslations();
  const [open, setOpen] = useState(false);

  if (!user || !token) {
    return (
      <Link href="/login" className={CTA}>
        {t.pricing.subscribeSignIn}
      </Link>
    );
  }
  if (!user.is_verified) {
    return (
      <Link href="/account" className={CTA}>
        {t.pricing.subscribeVerify}
      </Link>
    );
  }

  return (
    <>
      <button type="button" className={CTA} onClick={() => setOpen(true)}>
        {t.pricing.subscribeCta}
      </button>
      <SubscribeDialog
        open={open}
        plan={plan}
        planName={planName}
        amountPence={amountPence}
        termsVersion={termsVersion}
        token={token}
        onClose={() => setOpen(false)}
      />
    </>
  );
}
