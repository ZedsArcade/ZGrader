"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Checkbox } from "@heroui/react";
import Button from "@/components/Button";
import * as api from "@/lib/api";
import { useTranslations } from "@/lib/i18n/context";
import { toastError } from "@/lib/toast";
import { useMoney } from "@/lib/use-pricing";

/**
 * The last step before Stripe's payment page: what it costs, and the two
 * things the server refuses to proceed without -- acceptance of the Terms
 * version it currently enforces, and consent to start immediately. The
 * amount shown is the catalog's; the server decides the real one, and
 * Stripe's page shows it again before anyone pays.
 */
export default function SubscribeDialog({
  open,
  plan,
  planName,
  amountPence,
  termsVersion,
  token,
  onClose,
}: {
  open: boolean;
  plan: api.PricedPlan;
  planName: string;
  amountPence: number;
  termsVersion: string;
  token: string;
  onClose: () => void;
}) {
  const t = useTranslations();
  const money = useMoney();
  const [terms, setTerms] = useState(false);
  const [immediate, setImmediate] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (open) return;
    setTerms(false);
    setImmediate(false);
    setBusy(false);
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !busy) onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, busy, onClose]);

  if (!open) return null;

  const period = plan.billing_period === "year" ? t.pricing.perYear : t.pricing.perMonth;

  async function proceed() {
    setBusy(true);
    try {
      const { url } = await api.startCheckout(token, plan.plan, termsVersion);
      // A full navigation: Stripe's page is a different origin.
      window.location.href = url;
    } catch (err) {
      toastError(err instanceof Error ? err.message : t.pricing.checkoutFailed);
      setBusy(false);
    }
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="subscribe-title"
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
    >
      <div className="absolute inset-0 bg-black/60" onClick={busy ? undefined : onClose} />
      <div className="relative z-10 w-full max-w-md rounded-2xl border border-border bg-surface p-6 shadow-xl">
        <h2 id="subscribe-title" className="text-lg font-semibold text-foreground">
          {t.pricing.confirmTitle.replace("{plan}", planName)}
        </h2>
        <p className="mt-2 text-sm text-muted">
          {t.pricing.confirmBody.replace("{price}", money(amountPence)).replace("{period}", period)}
        </p>

        <div className="mt-4 flex flex-col gap-3">
          <Checkbox.Root isSelected={terms} onChange={setTerms}>
            <Checkbox.Content>
              <Checkbox.Control>
                <Checkbox.Indicator />
              </Checkbox.Control>
              <span className="text-sm">{t.pricing.confirmTerms}</span>
            </Checkbox.Content>
          </Checkbox.Root>
          <p className="text-xs text-muted">
            <Link
              href="/terms"
              target="_blank"
              className="-my-2 inline-block py-2 text-accent underline-offset-2 hover:underline"
            >
              {t.pricing.confirmReadTerms}
            </Link>
            {" · "}
            <Link
              href="/refunds"
              target="_blank"
              className="-my-2 inline-block py-2 text-accent underline-offset-2 hover:underline"
            >
              {t.pricing.confirmReadRefunds}
            </Link>
          </p>
          <Checkbox.Root isSelected={immediate} onChange={setImmediate}>
            <Checkbox.Content>
              <Checkbox.Control>
                <Checkbox.Indicator />
              </Checkbox.Control>
              <span className="text-sm">{t.pricing.confirmImmediate}</span>
            </Checkbox.Content>
          </Checkbox.Root>
        </div>

        <div className="mt-6 flex justify-end gap-2">
          <Button variant="outline" onPress={onClose} isDisabled={busy}>
            {t.pricing.confirmCancel}
          </Button>
          <Button variant="primary" onPress={proceed} isDisabled={busy || !terms || !immediate}>
            {busy ? t.pricing.confirmRedirecting : t.pricing.confirmContinue}
          </Button>
        </div>
      </div>
    </div>
  );
}
