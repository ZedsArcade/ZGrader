"use client";

import Link from "next/link";
import { Card, Chip, buttonVariants, cn } from "@heroui/react";
import * as api from "@/lib/api";
import { useTranslations } from "@/lib/i18n/context";
import { useServiceImages } from "@/lib/use-service-images";

export type Availability = "available" | "soon" | "planned";

export interface ServiceTier {
  // The stable identity: it keys the React list and links the tier to its
  // uploaded banner. The translated name can't do either job -- it changes
  // when the locale does.
  slug: api.ServiceSlug;
  name: string;
  body: string;
  points: string[];
  status: Availability;
  warning?: string;
  // Set only where there is a real page behind it.
  learnMoreHref?: string;
}

const STATUS_COLOR: Record<Availability, "success" | "warning" | "default"> = {
  available: "success",
  soon: "warning",
  planned: "default",
};

/**
 * Renders a set of service tiers as cards.
 *
 * Extracted when the services page split in two: GemLab and GemCare list
 * different tiers but present them identically, and duplicating this markup
 * would have guaranteed the two drifted apart.
 */
export default function ServiceTierGrid({ tiers }: { tiers: ServiceTier[] }) {
  const t = useTranslations();
  const { images } = useServiceImages();

  const statusLabel: Record<Availability, string> = {
    available: t.services.statusAvailable,
    soon: t.services.statusComingSoon,
    planned: t.services.statusPlanned,
  };

  return (
    <div className="verdict-reveal grid gap-5 sm:grid-cols-2">
      {tiers.map((tier) => (
        <Card key={tier.slug} className="interactive-card flex flex-col overflow-hidden">
          {/* Only tiers the operator has given an image get one; the rest
              render exactly as they did before, so a half-filled page still
              looks deliberate.

              A plain src, unlike every other image in this app: these are
              marketing images on a public page, so there's no token to attach
              and no need for the fetch-to-blob dance. */}
          {images[tier.slug] !== undefined && (
            // eslint-disable-next-line @next/next/no-img-element
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
            <div className="mt-auto flex flex-wrap items-center gap-3 pt-2">
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
              {tier.learnMoreHref && (
                <Link
                  href={tier.learnMoreHref}
                  className="text-sm font-semibold text-accent link-accent-hover hover:underline"
                >
                  {t.services.methodologyCta} &rsaquo;
                </Link>
              )}
            </div>
          </Card.Content>
        </Card>
      ))}
    </div>
  );
}
