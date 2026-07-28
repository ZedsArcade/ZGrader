"use client";

import LegalSection from "@/components/LegalSection";
import PageHeader from "@/components/PageHeader";
import { useTranslations } from "@/lib/i18n/context";
import { useBusinessName, withBusinessName } from "@/lib/use-business-name";

export default function PrivacyClient() {
  const t = useTranslations();
  const businessName = useBusinessName();

  const sections = [
    { title: t.privacy.s1Title, body: t.privacy.s1Body },
    { title: t.privacy.s2Title, body: t.privacy.s2Body },
    { title: t.privacy.s3Title, body: t.privacy.s3Body },
    { title: t.privacy.s4Title, body: t.privacy.s4Body },
    { title: t.privacy.s5Title, body: t.privacy.s5Body },
    { title: t.privacy.s6Title, body: t.privacy.s6Body },
    { title: t.privacy.s7Title, body: t.privacy.s7Body },
    { title: t.privacy.s8Title, body: t.privacy.s8Body },
    { title: t.privacy.s9Title, body: t.privacy.s9Body },
  ];

  return (
    <div className="max-w-3xl">
      <PageHeader
        title={t.privacy.title}
        lede={withBusinessName(t.privacy.intro, businessName)}
        meta={`${t.privacy.updated}: ${t.privacy.updatedValue}`}
      />

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
        {t.privacy.reviewNote}
      </p>
    </div>
  );
}
