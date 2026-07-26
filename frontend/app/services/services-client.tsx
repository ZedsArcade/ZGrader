"use client";

import Link from "next/link";
import { Card, Chip, buttonVariants, cn } from "@heroui/react";
import PageHeader from "@/components/PageHeader";
import * as api from "@/lib/api";
import { useTranslations } from "@/lib/i18n/context";
import { useGradingCompanies, withCompanies } from "@/lib/use-grading-companies";
import { useServiceImages } from "@/lib/use-service-images";

type Availability = "available" | "soon" | "planned";

const STATUS_COLOR: Record<Availability, "success" | "warning" | "default"> = {
  available: "success",
  soon: "warning",
  planned: "default",
};

export default function ServicesClient() {
  const t = useTranslations();
  const { images } = useServiceImages();
  const companies = useGradingCompanies();

  const statusLabel: Record<Availability, string> = {
    available: t.services.statusAvailable,
    soon: t.services.statusComingSoon,
    planned: t.services.statusPlanned,
  };

  // `slug` is the stable identity: it keys the React list and links the tier
  // to its uploaded banner. The translated name can't do either job -- it
  // changes when the locale does.
  const tiers: {
    slug: api.ServiceSlug;
    name: string;
    body: string;
    points: string[];
    status: Availability;
    warning?: string;
  }[] = [
    {
      slug: "analysis",
      name: t.services.tier1Name,
      body: t.services.tier1Body,
      points: [
        t.services.tier1Point1,
        t.services.tier1Point2,
        withCompanies(t.services.tier1Point3, companies),
        t.services.tier1Point4,
      ],
      status: "available",
    },
    {
      slug: "subscription",
      name: t.services.tier2Name,
      body: t.services.tier2Body,
      points: [t.services.tier2Point1, t.services.tier2Point2, t.services.tier2Point3],
      status: "soon",
    },
    {
      slug: "personalised",
      name: t.services.tier3Name,
      body: t.services.tier3Body,
      points: [t.services.tier3Point1, t.services.tier3Point2, t.services.tier3Point3],
      status: "soon",
    },
    {
      slug: "restoration",
      name: t.services.tier4Name,
      body: t.services.tier4Body,
      points: [t.services.tier4Point1, t.services.tier4Point2, t.services.tier4Point3],
      status: "soon",
      warning: t.services.tier4Warning,
    },
    {
      slug: "packaging",
      name: t.services.tier5Name,
      body: t.services.tier5Body,
      points: [t.services.tier5Point1, t.services.tier5Point2, t.services.tier5Point3],
      status: "planned",
    },
    {
      slug: "collection",
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
          <Card key={tier.slug} className="interactive-card flex flex-col overflow-hidden">
            {/* Only tiers the operator has given an image get one; the rest
                render exactly as they did before, so a half-filled Services
                page still looks deliberate.

                A plain src, unlike every other image in this app: these are
                marketing images on a public page, so there's no token to
                attach and no need for the fetch-to-blob dance. */}
            {images[tier.slug] !== undefined && (
              <img
                src={api.serviceImageUrl(tier.slug, images[tier.slug]!)}
                alt=""
                className="aspect-video w-full object-cover"
              />
            )}
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
