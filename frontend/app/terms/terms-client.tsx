"use client";

import { Card } from "@heroui/react";
import LegalSection from "@/components/LegalSection";
import PageHeader from "@/components/PageHeader";
import { useTranslations } from "@/lib/i18n/context";
import { useBusinessName, withBusinessName } from "@/lib/use-business-name";

export default function TermsClient() {
  const t = useTranslations();
  const businessName = useBusinessName();

  const sections = [
    { title: t.terms.s1Title, body: t.terms.s1Body },
    { title: t.terms.s2Title, body: t.terms.s2Body },
    { title: t.terms.s3Title, body: t.terms.s3Body },
    { title: t.terms.s4Title, body: t.terms.s4Body },
    { title: t.terms.s5Title, body: t.terms.s5Body },
    { title: t.terms.s6Title, body: t.terms.s6Body },
    { title: t.terms.s7Title, body: t.terms.s7Body },
    { title: t.terms.s8Title, body: t.terms.s8Body },
    { title: t.terms.s9Title, body: t.terms.s9Body },
    { title: t.terms.s10Title, body: t.terms.s10Body },
    { title: t.terms.s11Title, body: t.terms.s11Body },
  ];

  return (
    <div className="max-w-3xl">
      <PageHeader
        title={t.terms.title}
        lede={withBusinessName(t.terms.intro, businessName)}
        meta={`${t.terms.updated}: ${t.terms.updatedValue}`}
      />

      {/* The disclaimer leads the page and is visually separated, because it's
          the one clause a customer most needs to have read. Its report-side
          twin is Settings.disclaimer_text on the backend. */}
      <Card
        id="disclaimer"
        className="scroll-mt-24 border-l-4"
        style={{ borderLeftColor: "var(--neon-pink)" }}
      >
        <Card.Header>
          <Card.Title>{t.terms.disclaimerTitle}</Card.Title>
        </Card.Header>
        <Card.Content>
          <p className="text-sm leading-relaxed text-foreground">
            {withBusinessName(t.terms.disclaimerBody, businessName)}
          </p>
        </Card.Content>
      </Card>

      {/* Bodies go through withBusinessName so a renamed business is reflected
          in the legal text too, not just the marketing copy. */}
      <div className="mt-8 flex flex-col gap-6">
        {sections.map((section) => (
          <LegalSection
            key={section.title}
            title={section.title}
            body={withBusinessName(section.body, businessName)}
          />
        ))}
      </div>

      <p className="mt-8 border-t border-border pt-4 text-xs italic text-muted">
        {t.terms.reviewNote}
      </p>
    </div>
  );
}
