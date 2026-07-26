"use client";

import Link from "next/link";
import { Card, Chip, buttonVariants, cn } from "@heroui/react";
import PageHeader from "@/components/PageHeader";
import { useTranslations } from "@/lib/i18n/context";

type Availability = "available" | "soon" | "planned";

const STATUS_COLOR: Record<Availability, "success" | "warning" | "default"> = {
  available: "success",
  soon: "warning",
  planned: "default",
};

export default function ServicesClient() {
  const t = useTranslations();

  const statusLabel: Record<Availability, string> = {
    available: t.services.statusAvailable,
    soon: t.services.statusComingSoon,
    planned: t.services.statusPlanned,
  };

  const tiers: {
    name: string;
    body: string;
    points: string[];
    status: Availability;
    warning?: string;
  }[] = [
    {
      name: t.services.tier1Name,
      body: t.services.tier1Body,
      points: [
        t.services.tier1Point1,
        t.services.tier1Point2,
        t.services.tier1Point3,
        t.services.tier1Point4,
      ],
      status: "available",
    },
    {
      name: t.services.tier2Name,
      body: t.services.tier2Body,
      points: [t.services.tier2Point1, t.services.tier2Point2, t.services.tier2Point3],
      status: "soon",
    },
    {
      name: t.services.tier3Name,
      body: t.services.tier3Body,
      points: [t.services.tier3Point1, t.services.tier3Point2, t.services.tier3Point3],
      status: "soon",
    },
    {
      name: t.services.tier4Name,
      body: t.services.tier4Body,
      points: [t.services.tier4Point1, t.services.tier4Point2, t.services.tier4Point3],
      status: "soon",
      warning: t.services.tier4Warning,
    },
    {
      name: t.services.tier5Name,
      body: t.services.tier5Body,
      points: [t.services.tier5Point1, t.services.tier5Point2, t.services.tier5Point3],
      status: "planned",
    },
    {
      name: t.services.tier6Name,
      body: t.services.tier6Body,
      points: [t.services.tier6Point1, t.services.tier6Point2, t.services.tier6Point3],
      status: "planned",
    },
  ];

  return (
    <>
      <PageHeader title={t.services.title} lede={t.services.subtitle} />

      <div className="verdict-reveal grid gap-5 sm:grid-cols-2">
        {tiers.map((tier) => (
          <Card key={tier.name} className="interactive-card flex flex-col">
            <Card.Header>
              <div className="flex flex-wrap items-center gap-2">
                <Card.Title>{tier.name}</Card.Title>
                <Chip size="sm" color={STATUS_COLOR[tier.status]} variant="soft">
                  {statusLabel[tier.status]}
                </Chip>
              </div>
            </Card.Header>
            <Card.Content className="flex flex-1 flex-col gap-3">
              <p className="text-sm text-muted">{tier.body}</p>
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-muted">
                  {t.services.includesLabel}
                </p>
                <ul className="mt-2 flex flex-col gap-1.5">
                  {tier.points.map((point) => (
                    <li key={point} className="flex gap-2 text-sm text-muted">
                      <span aria-hidden="true" className="text-accent">
                        &bull;
                      </span>
                      <span>{point}</span>
                    </li>
                  ))}
                </ul>
              </div>
              {tier.warning && (
                <p className="rounded-lg border border-dashed border-border bg-surface-secondary p-3 text-xs leading-relaxed text-muted">
                  {tier.warning}
                </p>
              )}
              {/* Unavailable tiers route to contact rather than presenting a
                  dead call to action. */}
              <div className="mt-auto pt-2">
                {tier.status === "available" ? (
                  <Link
                    href="/register"
                    className={cn(
                      buttonVariants({ variant: "primary", size: "sm" }),
                      "btn-press btn-neon-hover"
                    )}
                  >
                    {t.services.startCta}
                  </Link>
                ) : (
                  <Link
                    href="/contact"
                    className={cn(buttonVariants({ variant: "outline", size: "sm" }), "btn-press")}
                  >
                    {t.services.contactCta}
                  </Link>
                )}
              </div>
            </Card.Content>
          </Card>
        ))}
      </div>

      <Card className="mt-6">
        <Card.Content>
          <p className="text-sm text-muted">{t.services.pricingNote}</p>
        </Card.Content>
      </Card>
    </>
  );
}
