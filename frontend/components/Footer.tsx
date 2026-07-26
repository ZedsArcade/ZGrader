"use client";

import Link from "next/link";
import type { ComponentType } from "react";
import {
  FacebookIcon,
  InstagramIcon,
  WhatsAppIcon,
  XIcon,
  type IconProps,
} from "@/components/icons";
import { useBranding } from "@/lib/branding-context";
import { useTranslations } from "@/lib/i18n/context";

interface SocialLink {
  href: string;
  label: string;
  icon: ComponentType<IconProps>;
}

export default function Footer() {
  const t = useTranslations();
  const {
    business_name,
    contact_email,
    social_instagram,
    social_facebook,
    social_x,
    social_whatsapp,
  } = useBranding();

  // Every entry is conditional on its setting: an operator who doesn't use a
  // network leaves it blank in admin and it simply isn't rendered, rather
  // than the footer carrying a link that goes nowhere.
  const socials: SocialLink[] = [];
  if (social_instagram)
    socials.push({ href: social_instagram, label: t.footer.instagram, icon: InstagramIcon });
  if (social_facebook)
    socials.push({ href: social_facebook, label: t.footer.facebook, icon: FacebookIcon });
  if (social_x) socials.push({ href: social_x, label: t.footer.x, icon: XIcon });
  // The WhatsApp link is built here from a stored phone number, so an
  // operator-supplied URL scheme never reaches an href.
  if (social_whatsapp)
    socials.push({
      href: `https://wa.me/${social_whatsapp}`,
      label: t.footer.whatsapp,
      icon: WhatsAppIcon,
    });

  const explore = [
    { href: "/about", label: t.nav.about },
    { href: "/services", label: t.nav.services },
    { href: "/how-it-works", label: t.nav.howItWorks },
    { href: "/contact", label: t.nav.contact },
  ];
  const legal = [
    { href: "/terms", label: t.nav.terms },
    { href: "/privacy", label: t.nav.privacy },
  ];

  return (
    <footer className="border-t border-border bg-surface">
      <div className="mx-auto grid w-full max-w-5xl gap-8 px-5 py-10 sm:grid-cols-2 lg:grid-cols-4">
        <div className="lg:col-span-1">
          <p className="text-sm font-semibold text-foreground">{business_name}</p>
          <p className="mt-2 max-w-xs text-sm text-muted">{t.footer.tagline}</p>
        </div>

        <FooterColumn heading={t.footer.exploreHeading} links={explore} />
        <FooterColumn heading={t.footer.legalHeading} links={legal} />

        <div>
          <h2 className="text-sm font-semibold text-foreground">{t.footer.connectHeading}</h2>
          {contact_email && (
            <a
              href={`mailto:${contact_email}`}
              className="mt-3 block text-sm text-muted link-accent-hover hover:text-accent"
            >
              {contact_email}
            </a>
          )}
          {socials.length > 0 && (
            <ul className="mt-3 flex flex-wrap items-center gap-3">
              {socials.map(({ href, label, icon: Icon }) => (
                <li key={href}>
                  <a
                    href={href}
                    target="_blank"
                    rel="noopener noreferrer"
                    aria-label={label}
                    title={label}
                    className="inline-flex text-muted link-accent-hover hover:text-accent"
                  >
                    <Icon />
                  </a>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      <div className="border-t border-border">
        <p className="mx-auto w-full max-w-5xl px-5 py-4 text-xs text-muted">
          &copy; {new Date().getFullYear()} {business_name}. {t.footer.rights}
        </p>
      </div>
    </footer>
  );
}

function FooterColumn({
  heading,
  links,
}: {
  heading: string;
  links: { href: string; label: string }[];
}) {
  return (
    <div>
      <h2 className="text-sm font-semibold text-foreground">{heading}</h2>
      <ul className="mt-3 flex flex-col gap-2">
        {links.map(({ href, label }) => (
          <li key={href}>
            <Link href={href} className="text-sm text-muted link-accent-hover hover:text-accent">
              {label}
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
