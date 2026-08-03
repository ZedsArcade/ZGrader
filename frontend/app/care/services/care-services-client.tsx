"use client";

import { Card } from "@heroui/react";
import PageHeader from "@/components/PageHeader";
import OtherBrandServices from "@/components/OtherBrandServices";
import ServiceTierGrid, { type ServiceTier } from "@/components/ServiceTierGrid";
import { useTranslations } from "@/lib/i18n/context";

/**
 * GemCare's services: everything that involves physically handling someone
 * else's card. The analysis tiers live on GemLab's page instead.
 *
 * The tier copy is shared with that page (`t.services.tier4*` onwards) rather
 * than duplicated -- the split is about which page shows which tier, not about
 * rewriting any of them.
 */
export default function CareServicesClient() {
  const t = useTranslations();

  const tiers: ServiceTier[] = [
    {
      slug: "restoration",
      name: t.services.tier4Name,
      body: t.services.tier4Body,
      points: [t.services.tier4Point1, t.services.tier4Point2, t.services.tier4Point3],
      status: "soon",
      warning: t.services.tier4Warning,
      learnMoreHref: "/care",
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
      <PageHeader title={t.care.servicesTitle} lede={t.care.servicesLede} />
      <ServiceTierGrid tiers={tiers} />

      <Card className="mt-6">
        <Card.Content>
          <p className="text-sm text-muted">{t.services.pricingNote}</p>
        </Card.Content>
      </Card>

      <OtherBrandServices other="lab" />
    </>
  );
}
