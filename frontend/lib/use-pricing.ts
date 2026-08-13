"use client";

import { useEffect, useState } from "react";
import * as api from "@/lib/api";
import { useLocale } from "@/lib/i18n/context";

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
