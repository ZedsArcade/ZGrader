"use client";

import Link from "next/link";
import { Card, buttonVariants, cn } from "@heroui/react";
import PageHeader from "@/components/PageHeader";
import { useTranslations } from "@/lib/i18n/context";
import { useBranding } from "@/lib/branding-context";
import { withBusinessName } from "@/lib/use-business-name";

export default function CareClient() {
  const t = useTranslations();
  // The care brand, not business_name -- this whole section is the other side
  // of the business, and both names are operator-editable.
  const { care_business_name } = useBranding();

  const sections = [
    { title: t.care.s1Title, body: t.care.s1Body },
    { title: t.care.s2Title, body: t.care.s2Body },
    { title: t.care.s3Title, body: t.care.s3Body },
  ];

  return (
    <>
      <PageHeader title={t.care.title} lede={t.care.lede} />

      <p className="max-w-3xl text-base leading-relaxed text-muted">
        {withBusinessName(t.care.intro, care_business_name)}
      </p>

      <div className="mt-8 flex flex-wrap gap-3">
        <Link
          href="/contact"
          className={cn(buttonVariants({ variant: "primary" }), "btn-press btn-neon-hover")}
        >
          {t.care.ctaPrimary}
        </Link>
        <Link
          href="/"
          className={cn(buttonVariants({ variant: "outline" }), "btn-press btn-neon-hover")}
        >
          {t.care.ctaSecondary}
        </Link>
      </div>

      <div className="mt-10 grid gap-4 sm:grid-cols-3">
        {sections.map((section) => (
          <Card key={section.title}>
            <Card.Header>
              <Card.Title>{section.title}</Card.Title>
            </Card.Header>
            <Card.Content>
              <p className="text-sm leading-relaxed text-muted">{section.body}</p>
            </Card.Content>
          </Card>
        ))}
      </div>

      {/* Leads with the risk rather than burying it, the same way the terms
          page puts its disclaimer above the numbered clauses. */}
      <Card className="mt-10 border-l-4" style={{ borderLeftColor: "var(--neon-pink)" }}>
        <Card.Header>
          <Card.Title>{t.care.warningTitle}</Card.Title>
        </Card.Header>
        <Card.Content>
          <p className="text-sm leading-relaxed text-foreground">{t.care.warningBody}</p>
        </Card.Content>
      </Card>
    </>
  );
}
