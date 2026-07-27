"use client";

import { Card } from "@heroui/react";
import LegalSection from "@/components/LegalSection";
import PageHeader from "@/components/PageHeader";
import { useTranslations } from "@/lib/i18n/context";

export default function TermsClient() {
  const t = useTranslations();

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
        lede={t.terms.intro}
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
          <p className="text-sm leading-relaxed text-foreground">{t.terms.disclaimerBody}</p>
        </Card.Content>
      </Card>

      <div className="mt-8 flex flex-col gap-6">
        {sections.map((section) => (
          <LegalSection key={section.title} title={section.title} body={section.body} />
        ))}
      </div>

      <p className="mt-8 border-t border-border pt-4 text-xs italic text-muted">
        {t.terms.reviewNote}
      </p>
    </div>
  );
}
