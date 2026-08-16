"use client";

import { useEffect, useState } from "react";
import * as api from "@/lib/api";
import { useLocale, useTranslations } from "@/lib/i18n/context";

/**
 * Every published price, fetched from the rows that define them.
 *
 * Deliberately *not* held in the site copy. The figures are operator-tunable
 * from the admin panel, so a page that hardcoded them would start lying the
 * moment one was changed -- which is exactly what had happened before this:
 * the copy promised "the first check is free" while the seeded free plan
 * granted three a week.
 *
 * Returns null until loaded. Callers render a skeleton rather than a zero,
 * because a price of £0 shown briefly is worse than no price at all.
 */
export function usePricing(): api.Pricing | null {
  const [pricing, setPricing] = useState<api.Pricing | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .fetchPricing()
      .then((data) => {
        if (!cancelled) setPricing(data);
      })
      .catch(() => {
        // Leaving it null keeps the skeleton up. The alternative -- showing
        // stale or invented numbers when the API is unreachable -- would put a
        // price on the shopfront that nothing stands behind.
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return pricing;
}

/** The plan a user is on while they hold no subscription. Mirrors FREE_PLAN in
 *  `backend/zgrader/models/plan_entitlement.py`, which is the definition. */
const FREE_PLAN = "free";

/**
 * The free tier, or null if the operator has removed it.
 *
 * Found by name rather than by position. The catalog happens to sort by price
 * with nulls first, so the free plan is `plans[0]` today -- but that is a sort
 * order, not a contract, and a plan added at £0 would quietly take its place.
 */
export function freePlan(pricing: api.Pricing): api.PricedPlan | null {
  return (
    pricing.plans.find((p) => p.plan === FREE_PLAN) ??
    pricing.plans.find((p) => p.price_pence === null) ??
    null
  );
}

/**
 * What a plan grants, as a sentence fragment: "3 checks every 7 days".
 *
 * Lives here rather than on the pricing page because the marketing copy quotes
 * it too, and two descriptions of one allowance is the bug this whole
 * arrangement exists to prevent.
 */
export function useAllowanceLabel(): (plan: api.PricedPlan) => string {
  const t = useTranslations();
  return (plan) => {
    if (plan.submission_limit === null) return t.pricing.checksUnlimited;
    // A one-off pack is bought, not renewed. Quoting its window would read as
    // "25 checks every 365 days", which describes a subscription -- the exact
    // opposite of what the pack is. The window exists only because the quota
    // model has no persistent balance; see the seed comment.
    if (plan.billing_period === "once") {
      return t.pricing.checksOneOff.replace("{count}", String(plan.submission_limit));
    }
    return t.pricing.checksPerPeriod
      .replace("{count}", String(plan.submission_limit))
      .replace("{days}", String(plan.period_days));
  };
}

/**
 * "Free accounts get 3 checks every 7 days.", or null until the catalog says.
 *
 * Callers append it to a sentence that already stands on its own, so a page
 * that cannot reach the API loses the figure rather than showing a gap. That
 * is the opposite of what /pricing does with a skeleton, deliberately: a price
 * list missing a price is not a price list, but a call to action missing a
 * number is still a call to action.
 */
export function useFreeAllowanceSentence(): string | null {
  const pricing = usePricing();
  const allowance = useAllowanceLabel();
  const t = useTranslations();
  const { locale } = useLocale();

  const plan = pricing === null ? null : freePlan(pricing);
  if (plan === null) return null;
  // The label is written for a card heading, so the unlimited case arrives
  // capitalised -- "Free accounts get Unlimited checks." Dropping the first
  // letter's case fixes it and touches nothing else: the counted forms start
  // with a digit. Both languages lowercase mid-sentence, and
  // toLocaleLowerCase keeps the Spanish accent ("Análisis" -> "análisis").
  const fragment = allowance(plan);
  const lowered = fragment.charAt(0).toLocaleLowerCase(locale) + fragment.slice(1);
  return t.pricing.freeAllowance.replace("{allowance}", lowered);
}

/**
 * Whole pence to a readable amount: 450 becomes "£4.50", 500 becomes "£5".
 *
 * Trailing ".00" is dropped because a price list reads better without it, and
 * the two forms sit side by side here -- £4.50 next to £5 rather than £5.00.
 * `Intl` supplies the locale's own separators, so the Spanish page gets
 * "4,50 £" without a second implementation.
 */
export function useMoney(): (pence: number) => string {
  const { locale } = useLocale();
  return (pence: number) => {
    const whole = pence % 100 === 0;
    return new Intl.NumberFormat(locale, {
      style: "currency",
      currency: "GBP",
      minimumFractionDigits: whole ? 0 : 2,
      maximumFractionDigits: 2,
    }).format(pence / 100);
  };
}

/**
 * How a volume band reads on its own: "1 card", "2-9", "25+".
 *
 * A null `max_qty` is the open-ended top band, which is why it is nullable in
 * the database rather than a large sentinel -- "and up" stays unambiguous
 * everywhere it is read.
 */
export function bandLabel(tier: api.PhysicalPriceTier): string {
  if (tier.max_qty === null) return `${tier.min_qty}+`;
  if (tier.max_qty === tier.min_qty) return `${tier.min_qty}`;
  return `${tier.min_qty}–${tier.max_qty}`;
}
