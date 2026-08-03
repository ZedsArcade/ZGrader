"use client";

import Link from "next/link";
import { Card, buttonVariants, cn } from "@heroui/react";
import { useBranding } from "@/lib/branding-context";
import { CARE_PREFIX, type Brand } from "@/lib/brand";
import { useTranslations } from "@/lib/i18n/context";
import { withBusinessName } from "@/lib/use-business-name";

/**
 * A short hand-off to the other brand's services page.
 *
 * This is what makes splitting the services in two safe. The objection to
 * separating them was that each brand's tiers become invisible to someone
 * looking at the other; a deliberate pointer closes that without either page
 * carrying tiers that don't belong to it. It also lets the two sides feed each
 * other -- someone pricing up a grading submission is exactly the person who
 * might want a card cleaned first.
 *
 * `other` is the brand being pointed *at*, not the one you're on. Its name
 * comes from Settings, so renaming either brand in admin renames it here too.
 */
export default function OtherBrandServices({ other }: { other: Brand }) {
  const t = useTranslations();
  const { business_name, care_business_name } = useBranding();

  const name = other === "care" ? care_business_name : business_name;
  const href = other === "care" ? `${CARE_PREFIX}/services` : "/services";
  const body = other === "care" ? t.services.crossToCareBody : t.services.crossToLabBody;
  const title = other === "care" ? t.services.crossToCareTitle : t.services.crossToLabTitle;

  return (
    <Card className="mt-6 border-l-4" style={{ borderLeftColor: "var(--neon-cyan)" }}>
      <Card.Header>
        <Card.Title>{withBusinessName(title, name)}</Card.Title>
      </Card.Header>
      <Card.Content className="flex flex-col gap-4">
        <p className="text-sm leading-relaxed text-muted">{withBusinessName(body, name)}</p>
        <div>
          <Link
            href={href}
            className={cn(buttonVariants({ variant: "outline", size: "sm" }), "btn-press")}
          >
            {withBusinessName(t.services.crossCta, name)}
          </Link>
        </div>
      </Card.Content>
    </Card>
  );
}
