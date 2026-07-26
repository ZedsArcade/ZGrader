"use client";

import type { ReactNode } from "react";
import { Card } from "@heroui/react";
import PageHeader from "@/components/PageHeader";
import { useBranding } from "@/lib/branding-context";
import { useTranslations } from "@/lib/i18n/context";

export default function ContactClient() {
  const t = useTranslations();
  const {
    contact_email,
    contact_location,
    contact_response_days,
    contact_in_person,
    social_whatsapp,
  } = useBranding();

  // Every row is driven by an admin setting, so the operator controls what
  // appears here without a redeploy. If none is filled in we say so plainly
  // rather than rendering an empty page.
  const hasAnything =
    Boolean(contact_email) ||
    Boolean(contact_location) ||
    Boolean(social_whatsapp) ||
    contact_response_days !== null ||
    contact_in_person;

  return (
    <>
      <PageHeader title={t.contact.title} lede={t.contact.subtitle} />

      {!hasAnything ? (
        <Card>
          <Card.Header>
            <Card.Title>{t.contact.noneTitle}</Card.Title>
          </Card.Header>
          <Card.Content>
            <p className="text-sm text-muted">{t.contact.noneBody}</p>
          </Card.Content>
        </Card>
      ) : (
        <div className="verdict-reveal grid gap-5 sm:grid-cols-2">
          {contact_email && (
            <ContactCard label={t.contact.emailLabel}>
              <a
                href={`mailto:${contact_email}`}
                className="text-sm font-medium text-accent link-accent-hover"
              >
                {contact_email}
              </a>
            </ContactCard>
          )}

          {social_whatsapp && (
            <ContactCard label={t.contact.whatsappLabel}>
              {/* Built from the stored number rather than a stored URL, so no
                  operator-supplied scheme can end up in this href. */}
              <a
                href={`https://wa.me/${social_whatsapp}`}
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm font-medium text-accent link-accent-hover"
              >
                {t.contact.whatsappCta}
              </a>
            </ContactCard>
          )}

          {contact_location && (
            <ContactCard label={t.contact.locationLabel}>
              <p className="text-sm text-muted">{contact_location}</p>
            </ContactCard>
          )}

          {contact_response_days !== null && (
            <ContactCard label={t.contact.responseLabel}>
              <p className="text-sm text-muted">
                {t.contact.responseBody.replace("{days}", String(contact_response_days))}
              </p>
            </ContactCard>
          )}

          {contact_in_person && (
            <ContactCard label={t.contact.inPersonLabel}>
              <p className="text-sm text-muted">{t.contact.inPersonBody}</p>
            </ContactCard>
          )}
        </div>
      )}

      <Card className="mt-6">
        <Card.Header>
          <Card.Title>{t.contact.consultationTitle}</Card.Title>
        </Card.Header>
        <Card.Content>
          <p className="text-sm text-muted">{t.contact.consultationBody}</p>
        </Card.Content>
      </Card>
    </>
  );
}

function ContactCard({ label, children }: { label: string; children: ReactNode }) {
  return (
    <Card className="interactive-card">
      <Card.Content>
        <p className="text-xs font-semibold uppercase tracking-wide text-muted">{label}</p>
        <div className="mt-2">{children}</div>
      </Card.Content>
    </Card>
  );
}
