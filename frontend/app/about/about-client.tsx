"use client";

import Link from "next/link";
import { Card, buttonVariants, cn } from "@heroui/react";
import PageHeader from "@/components/PageHeader";
import { useTranslations } from "@/lib/i18n/context";

export default function AboutClient() {
  const t = useTranslations();

  return (
    <>
      <PageHeader title={t.about.title} lede={t.about.lede} />

      <div className="flex max-w-3xl flex-col gap-4 text-base leading-relaxed text-muted">
        <p>{t.about.body1}</p>
        <p>{t.about.body2}</p>
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
