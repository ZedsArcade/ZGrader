"use client";

import { Card } from "@heroui/react";
import PageHeader from "@/components/PageHeader";
import OtherBrandServices from "@/components/OtherBrandServices";
import ServiceTierGrid, { type ServiceTier } from "@/components/ServiceTierGrid";
import { useTranslations } from "@/lib/i18n/context";
import { useGradingCompanies, withCompanies } from "@/lib/use-grading-companies";

/**
 * GemLab's services: everything about deciding whether a card is worth
 * submitting. The physical-handling tiers live on GemCare's page instead --
 * see app/care/services.
 */
export default function ServicesClient() {
  const t = useTranslations();
  const companies = useGradingCompanies();

  const tiers: ServiceTier[] = [
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
      learnMoreHref: "/methodology",
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
  ];

  return (
    <>
      <PageHeader title={t.services.title} lede={t.services.subtitle} />
      <ServiceTierGrid tiers={tiers} />

      <Card className="mt-6">
        <Card.Content>
          <p className="text-sm text-muted">{t.services.pricingNote}</p>
        </Card.Content>
      </Card>

      <OtherBrandServices other="care" />
    </>
  );
}
