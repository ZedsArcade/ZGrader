"use client";

import Link from "next/link";
import { Card } from "@heroui/react";
import PageHeader from "@/components/PageHeader";
import Skeleton from "@/components/Skeleton";
import StartCheckLink from "@/components/StartCheckLink";
import OtherBrandServices from "@/components/OtherBrandServices";
import { useTranslations } from "@/lib/i18n/context";
import SubscribeButton from "@/components/SubscribeButton";
import { useGradingCompanies, withCompanies } from "@/lib/use-grading-companies";
import { PLAN_COPY, bandLabel, useAllowanceLabel, useMoney, usePricing } from "@/lib/use-pricing";

export default function PricingClient() {
  const t = useTranslations();
  const companies = useGradingCompanies();
  const pricing = usePricing();
  const money = useMoney();
  // Shared with the marketing CTAs, which quote the free tier's allowance --
  // one formatter so the two pages cannot describe it differently.
  const allowance = useAllowanceLabel();

  const billingLabel: Record<string, string> = {
    month: t.pricing.perMonth,
    year: t.pricing.perYear,
    once: t.pricing.oneOff,
  };

  return (
    <>
      <PageHeader title={t.pricing.title} lede={t.pricing.subtitle} />

      {/* Software tiers */}
      <section className="mt-8">
        <h2 className="text-xl font-semibold text-foreground">{t.pricing.softwareHeading}</h2>
        <p className="mt-2 max-w-2xl text-sm text-muted">{t.pricing.softwareLede}</p>

        {pricing === null ? (
          <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {[0, 1, 2, 3].map((i) => (
              <Skeleton key={i} className="h-56 w-full rounded-xl" />
            ))}
          </div>
        ) : (
          <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {pricing.plans.map((plan) => {
              const copy = PLAN_COPY[plan.plan];
              const name = copy
                ? (t.pricing[copy.nameKey as keyof typeof t.pricing] as string)
                : plan.plan;
              const note = copy
                ? (t.pricing[copy.noteKey as keyof typeof t.pricing] as string)
                : null;
              const free = plan.price_pence === null;
              // What an annual buyer would be quoted while founder seats remain.
              // The server decides the real amount; Stripe's page shows it again.
              const founderQuote =
                plan.billing_period === "year" &&
                pricing.founder_price_pence != null &&
                (pricing.founder_seats_remaining ?? 0) > 0
                  ? pricing.founder_price_pence
                  : null;
              const sellable =
                pricing.billing_enabled && (plan.billing_period === "month" || plan.billing_period === "year");
              return (
                <Card key={plan.plan} className="flex flex-col">
                  <Card.Content className="flex flex-1 flex-col gap-3">
                    <p className="text-sm font-semibold text-foreground">{name}</p>
                    <p className="text-3xl font-bold tabular-nums text-foreground">
                      {/* £0 rather than the word again: the card is already
                          headed "Free", and repeating it reads as a mistake. */}
                      {free ? money(0) : money(plan.price_pence!)}
                      {!free && plan.billing_period && (
                        <span className="ml-1 text-sm font-normal text-muted">
                          {/* Leading space is for screen readers; ml-1 only
                              spaces it visually. */}
                          {" "}
                          {billingLabel[plan.billing_period] ?? plan.billing_period}
                        </span>
                      )}
                    </p>
                    <p className="text-sm font-medium text-foreground">{allowance(plan)}</p>
                    {note && <p className="text-sm text-muted">{note}</p>}
                    <div className="mt-auto pt-2">
                      {free ? (
                        <StartCheckLink className="inline-flex min-h-11 items-center text-sm font-semibold text-accent link-accent-hover hover:underline">
                          {t.pricing.freeCta}
                        </StartCheckLink>
                      ) : sellable ? (
                        <SubscribeButton
                          plan={plan}
                          planName={name}
                          amountPence={founderQuote ?? plan.price_pence!}
                          termsVersion={pricing.terms_version}
                        />
                      ) : (
                        <Link
                          href="/contact"
                          className="inline-flex min-h-11 items-center text-sm font-semibold text-accent link-accent-hover hover:underline"
                        >
                          {t.pricing.paidCta}
                        </Link>
                      )}
                    </div>
                  </Card.Content>
                </Card>
              );
            })}
          </div>
        )}
        {/* Only while nothing takes payments: say how a paid tier starts
            rather than letting someone find out at a dead end. */}
        {pricing !== null && !pricing.billing_enabled && (
          <p className="mt-3 text-sm text-muted">{t.pricing.paidNote}</p>
        )}
      </section>

      {/* In-hand pre-grading */}
      <section className="mt-10">
        <h2 className="text-xl font-semibold text-foreground">{t.pricing.physicalHeading}</h2>
        <p className="mt-2 max-w-2xl text-sm text-muted">{t.pricing.physicalLede}</p>

        <Card className="mt-4">
          <Card.Content>
            {pricing === null ? (
              <Skeleton className="h-40 w-full rounded-lg" />
            ) : (
              // Scrolls inside its own container rather than pushing the page
              // sideways on a phone -- the rule the whole site follows.
              <div className="overflow-x-auto">
                <table className="w-full min-w-[18rem] text-sm">
                  <thead>
                    <tr className="border-b border-border text-left text-muted">
                      <th className="py-2 pr-4 font-medium">{t.pricing.physicalQty}</th>
                      <th className="py-2 font-medium">{t.pricing.physicalPer}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {pricing.physical_tiers.map((tier) => (
                      <tr key={tier.min_qty} className="border-b border-border last:border-0">
                        <td className="py-2 pr-4 tabular-nums text-foreground">{bandLabel(tier)}</td>
                        <td className="py-2 font-semibold tabular-nums text-foreground">
                          {money(tier.price_pence)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            <ul className="mt-4 flex flex-col gap-1 text-sm text-muted">
              <li>{t.pricing.physicalTurnaround}</li>
              <li>{t.pricing.physicalLocation}</li>
              <li>{t.pricing.physicalPostage}</li>
            </ul>
            <Link
              href="/contact"
              className="mt-3 inline-flex min-h-11 items-center text-sm font-semibold text-accent link-accent-hover hover:underline"
            >
              {t.pricing.physicalCta}
            </Link>
          </Card.Content>
        </Card>
      </section>

      {/* Bundles */}
      <section className="mt-10">
        <h2 className="text-xl font-semibold text-foreground">{t.pricing.bundlesHeading}</h2>
        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          <Card>
            <Card.Content className="flex flex-col gap-2">
              <p className="text-sm font-semibold text-foreground">{t.pricing.triageName}</p>
              <p className="text-sm text-muted">{t.pricing.triageBody}</p>
              {pricing?.collection_triage_guide_pence != null && (
                <p className="text-sm text-muted">
                  {t.pricing.triageGuide.replace(
                    "{price}",
                    money(pricing.collection_triage_guide_pence)
                  )}
                </p>
              )}
              <Link
                href="/contact"
                className="mt-auto inline-flex min-h-11 items-center text-sm font-semibold text-accent link-accent-hover hover:underline"
              >
                {t.pricing.triageCta}
              </Link>
            </Card.Content>
          </Card>
          <Card>
            <Card.Content className="flex flex-col gap-2">
              <p className="text-sm font-semibold text-foreground">{t.pricing.doubleName}</p>
              <p className="text-sm text-muted">{t.pricing.doubleBody}</p>
            </Card.Content>
          </Card>
        </div>
      </section>

      {/* Subscriber extras -- each hidden when its figure is null, because null
          means the offer is switched off rather than free. */}
      {(pricing?.subscriber_discount_pct != null || pricing?.founder_price_pence != null) && (
        <section className="mt-10">
          <h2 className="text-xl font-semibold text-foreground">{t.pricing.extrasHeading}</h2>
          <ul className="mt-3 flex flex-col gap-2 text-sm text-muted">
            {pricing.subscriber_discount_pct != null && (
              <li>
                {t.pricing.discount.replace(
                  "{percent}",
                  String(pricing.subscriber_discount_pct)
                )}
              </li>
            )}
            {pricing.founder_price_pence != null &&
              pricing.founder_seats != null &&
              pricing.founder_seats_remaining !== 0 && (
                <li>
                  {t.pricing.founder
                    .replace("{seats}", String(pricing.founder_seats))
                    .replace("{price}", money(pricing.founder_price_pence))}
                  {pricing.billing_enabled && pricing.founder_seats_remaining != null && (
                    <>
                      {" "}
                      {t.pricing.founderRemaining
                        .replace("{remaining}", String(pricing.founder_seats_remaining))
                        .replace("{seats}", String(pricing.founder_seats))}
                    </>
                  )}
                </li>
              )}
          </ul>
        </section>
      )}

      <Card className="mt-8">
        <Card.Content>
          <p className="text-sm text-muted">{withCompanies(t.pricing.disclaimer, companies)}</p>
        </Card.Content>
      </Card>

      <OtherBrandServices other="care" />
    </>
  );
}
