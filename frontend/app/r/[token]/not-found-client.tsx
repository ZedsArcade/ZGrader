"use client";

import Link from "next/link";
import { Card, buttonVariants, cn } from "@heroui/react";
import PageHeader from "@/components/PageHeader";
import { useTranslations } from "@/lib/i18n/context";

/** A client component so this follows the viewer's own language like every
 *  other page -- the locale lives in localStorage and only the browser has it. */
export default function PublicReportNotFound() {
  const t = useTranslations();

  return (
    <>
      <PageHeader title={t.publicReport.notFoundTitle} lede={t.publicReport.notFoundBody} />
      <Card className="interactive-card">
        <Card.Header>
          <Card.Title>{t.publicReport.ctaTitle}</Card.Title>
        </Card.Header>
        <Card.Content>
          <p className="text-sm text-muted">{t.publicReport.ctaBody}</p>
          <div className="mt-4">
            <Link
              href="/register"
              className={cn(buttonVariants({ variant: "primary" }), "btn-press btn-neon-hover")}
            >
              {t.publicReport.ctaButton}
            </Link>
          </div>
        </Card.Content>
      </Card>
    </>
  );
}
