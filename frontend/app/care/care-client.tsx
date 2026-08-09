"use client";

import Link from "next/link";
import { Card, buttonVariants, cn } from "@heroui/react";
import BrandLink from "@/components/BrandLink";
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
      {/* Same enclosing hero as GemLab's landing (app/page.tsx): rounded-2xl,
          the radial --neon-glow wash, icon / title / lede / CTAs in that
          order. It was a bare PageHeader before, which made the two landings
          look like pages from different sites. The gradient needs no
          per-brand handling -- --neon-glow is already brand-scoped in
          tokens.css, so it resolves to jade here and magenta on GemLab. */}
      <section
        className="flex flex-col items-start gap-5 rounded-2xl px-6 py-14"
        style={{
          background:
            "radial-gradient(ellipse at top left, var(--neon-glow), transparent 60%), var(--bg)",
        }}
      >
        {/* A card in a sleeve -- this side of the business is about protecting
            what the customer already owns, where GemLab's icon is a card being
            measured. */}
        <svg width="40" height="40" viewBox="0 0 40 40" fill="none" aria-hidden="true" className="text-accent">
          <rect x="7" y="4" width="26" height="32" rx="3" stroke="currentColor" strokeWidth="1.5" />
          <path d="M7 10 H33" stroke="currentColor" strokeWidth="1.5" />
          <path d="M11 14 H29 M11 19 H29 M11 24 H24" stroke="currentColor" strokeWidth="1" opacity="0.6" />
        </svg>
        <h1 className="text-4xl font-bold tracking-tight text-foreground sm:text-5xl">
          {t.care.title}
        </h1>
        <p className="max-w-2xl text-lg text-muted">{t.care.lede}</p>
        <div className="flex flex-wrap gap-3">
          <Link
            href="/contact"
            className={cn(buttonVariants({ variant: "primary" }), "btn-press btn-neon-hover")}
          >
            {t.care.ctaPrimary}
          </Link>
          {/* BrandLink: "/" is shared between the brands, so a plain Link
              leaves the visitor on GemLab's home page in GemCare's palette. */}
          <BrandLink
            brand="lab"
            href="/"
            className={cn(buttonVariants({ variant: "outline" }), "btn-press btn-neon-hover")}
          >
            {t.care.ctaSecondary}
          </BrandLink>
        </div>
      </section>

      <p className="mt-8 max-w-3xl text-base leading-relaxed text-muted">
        {withBusinessName(t.care.intro, care_business_name)}
      </p>

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
