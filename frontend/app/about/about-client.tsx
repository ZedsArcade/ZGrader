"use client";

import Link from "next/link";
import { Card, buttonVariants, cn } from "@heroui/react";
import BrandLink from "@/components/BrandLink";
import PageHeader from "@/components/PageHeader";
import { CARE_PREFIX } from "@/lib/brand";
import { useBranding } from "@/lib/branding-context";
import { useTranslations } from "@/lib/i18n/context";
import { useBusinessName, withBusinessName } from "@/lib/use-business-name";

export default function AboutClient() {
  const t = useTranslations();
  const businessName = useBusinessName();
  // Both names are operator-editable and this page is the one place that
  // explains the difference between them, so neither can be hardcoded.
  const { care_business_name } = useBranding();

  return (
    <>
      <PageHeader title={t.about.title} lede={t.about.lede} />

      <div className="flex max-w-3xl flex-col gap-4 text-base leading-relaxed text-muted">
        <p>{withBusinessName(t.about.body1, businessName)}</p>
        <p>{t.about.body2}</p>
      </div>

      {/* The split is the thing most visitors arrive confused about, so it
          gets its own section rather than a sentence buried in the prose --
          one card per brand, each linking into that side of the site. */}
      <section className="mt-10">
        <h2 className="text-2xl font-bold tracking-tight text-foreground">{t.about.splitTitle}</h2>
        <p className="mt-2 max-w-2xl text-base leading-relaxed text-muted">{t.about.splitLede}</p>

        <div className="mt-6 grid gap-5 sm:grid-cols-2">
          <Card className="interactive-card">
            <Card.Header>
              <Card.Title>{withBusinessName(t.about.labTitle, businessName)}</Card.Title>
            </Card.Header>
            <Card.Content className="flex flex-col gap-4">
              <p className="text-sm leading-relaxed text-muted">{t.about.labBody}</p>
              <div>
                {/* BrandLink: /services belongs to both brands, so without
                    recording the target the visitor lands there still in
                    whichever palette they arrived in. */}
                <BrandLink
                  brand="lab"
                  href="/services"
                  className={cn(buttonVariants({ variant: "outline", size: "sm" }), "btn-press")}
                >
                  {withBusinessName(t.services.crossCta, businessName)}
                </BrandLink>
              </div>
            </Card.Content>
          </Card>

          <Card className="interactive-card">
            <Card.Header>
              <Card.Title>{withBusinessName(t.about.careTitle, care_business_name)}</Card.Title>
            </Card.Header>
            <Card.Content className="flex flex-col gap-4">
              <p className="text-sm leading-relaxed text-muted">{t.about.careBody}</p>
              <div>
                {/* Plain Link: /care/* forces the brand on arrival, so this
                    one needs no help. */}
                <Link
                  href={`${CARE_PREFIX}/services`}
                  className={cn(buttonVariants({ variant: "outline", size: "sm" }), "btn-press")}
                >
                  {withBusinessName(t.services.crossCta, care_business_name)}
                </Link>
              </div>
            </Card.Content>
          </Card>
        </div>
      </section>

      <div className="mt-10 flex max-w-3xl flex-col gap-4 text-base leading-relaxed text-muted">
        <p>{t.about.body3}</p>
      </div>

      <Card className="mt-8">
        <Card.Header>
          <Card.Title>{t.about.honestTitle}</Card.Title>
        </Card.Header>
        <Card.Content>
          <p className="text-sm text-muted">{t.about.honestBody}</p>
        </Card.Content>
      </Card>

      <Card className="interactive-card mt-5">
        <Card.Header>
          <Card.Title>{t.about.ctaTitle}</Card.Title>
        </Card.Header>
        <Card.Content>
          <p className="text-sm text-muted">{t.about.ctaBody}</p>
          <div className="mt-4 flex flex-wrap gap-3">
            <Link
              href="/register"
              className={cn(buttonVariants({ variant: "primary" }), "btn-press btn-neon-hover")}
            >
              {t.landing.getStarted}
            </Link>
            <Link
              href="/how-it-works"
              className={cn(buttonVariants({ variant: "outline" }), "btn-press")}
            >
              {t.nav.howItWorks}
            </Link>
          </div>
        </Card.Content>
      </Card>
    </>
  );
}
