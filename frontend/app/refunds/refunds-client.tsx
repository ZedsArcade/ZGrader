"use client";

import LegalSection from "@/components/LegalSection";
import PageHeader from "@/components/PageHeader";
import { useTranslations } from "@/lib/i18n/context";
import { useBusinessName, withBusinessName } from "@/lib/use-business-name";

export default function RefundsClient() {
  const t = useTranslations();
  const businessName = useBusinessName();

  const sections = [
    { title: t.refunds.s1Title, body: t.refunds.s1Body },
    { title: t.refunds.s2Title, body: t.refunds.s2Body },
    { title: t.refunds.s3Title, body: t.refunds.s3Body },
    { title: t.refunds.s4Title, body: t.refunds.s4Body },
    { title: t.refunds.s5Title, body: t.refunds.s5Body },
    { title: t.refunds.s6Title, body: t.refunds.s6Body },
    { title: t.refunds.s7Title, body: t.refunds.s7Body },
    { title: t.refunds.s8Title, body: t.refunds.s8Body },
  ];

  return (
    <div className="max-w-3xl">
      <PageHeader
        title={t.refunds.title}
        lede={withBusinessName(t.refunds.intro, businessName)}
        meta={`${t.refunds.updated}: ${t.refunds.updatedValue}`}
      />

      {/* Bodies go through withBusinessName so a renamed business is reflected
          in the legal text too, not just the marketing copy. */}
      <div className="flex flex-col gap-6">
        {sections.map((section) => (
          <LegalSection
            key={section.title}
            title={section.title}
            body={withBusinessName(section.body, businessName)}
          />
        ))}
      </div>

      <p className="mt-8 border-t border-border pt-4 text-xs italic text-muted">
        {t.refunds.reviewNote}
      </p>
    </div>
  );
}
