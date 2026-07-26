"use client";

import Link from "next/link";
import type { ComponentType } from "react";
import { useBranding } from "@/lib/branding-context";
import { useTranslations } from "@/lib/i18n/context";

/** Icons are inline SVG rather than an icon package -- the house idiom, and
 *  four glyphs isn't worth a dependency. `currentColor` so they follow the
 *  link colour in both themes. */
const ICON_PROPS = {
  width: 20,
  height: 20,
  viewBox: "0 0 24 24",
  fill: "currentColor",
  "aria-hidden": true,
} as const;

function InstagramIcon() {
  return (
    <svg {...ICON_PROPS}>
      <path d="M12 2c2.72 0 3.06.01 4.12.06 1.07.05 1.8.22 2.43.46.66.26 1.22.6 1.77 1.16.56.55.9 1.11 1.16 1.77.24.63.41 1.36.46 2.43.05 1.06.06 1.4.06 4.12s-.01 3.06-.06 4.12c-.05 1.07-.22 1.8-.46 2.43a4.9 4.9 0 0 1-1.16 1.77c-.55.56-1.11.9-1.77 1.16-.63.24-1.36.41-2.43.46-1.06.05-1.4.06-4.12.06s-3.06-.01-4.12-.06c-1.07-.05-1.8-.22-2.43-.46a4.9 4.9 0 0 1-1.77-1.16 4.9 4.9 0 0 1-1.16-1.77c-.24-.63-.41-1.36-.46-2.43C2.01 15.06 2 14.72 2 12s.01-3.06.06-4.12c.05-1.07.22-1.8.46-2.43.26-.66.6-1.22 1.16-1.77.55-.56 1.11-.9 1.77-1.16.63-.24 1.36-.41 2.43-.46C8.94 2.01 9.28 2 12 2Zm0 1.8c-2.67 0-2.99.01-4.04.06-.98.04-1.5.2-1.86.34-.47.18-.8.4-1.15.75-.35.35-.57.68-.75 1.15-.14.36-.3.88-.34 1.86-.05 1.05-.06 1.37-.06 4.04s.01 2.99.06 4.04c.04.98.2 1.5.34 1.86.18.47.4.8.75 1.15.35.35.68.57 1.15.75.36.14.88.3 1.86.34 1.05.05 1.37.06 4.04.06s2.99-.01 4.04-.06c.98-.04 1.5-.2 1.86-.34.47-.18.8-.4 1.15-.75.35-.35.57-.68.75-1.15.14-.36.3-.88.34-1.86.05-1.05.06-1.37.06-4.04s-.01-2.99-.06-4.04c-.04-.98-.2-1.5-.34-1.86a3.1 3.1 0 0 0-.75-1.15 3.1 3.1 0 0 0-1.15-.75c-.36-.14-.88-.3-1.86-.34-1.05-.05-1.37-.06-4.04-.06Zm0 3.07a5.13 5.13 0 1 1 0 10.26 5.13 5.13 0 0 1 0-10.26Zm0 8.46a3.33 3.33 0 1 0 0-6.66 3.33 3.33 0 0 0 0 6.66Zm6.54-8.66a1.2 1.2 0 1 1-2.4 0 1.2 1.2 0 0 1 2.4 0Z" />
    </svg>
  );
}

function FacebookIcon() {
  return (
    <svg {...ICON_PROPS}>
      <path d="M24 12.07C24 5.4 18.63 0 12 0S0 5.4 0 12.07C0 18.1 4.39 23.1 10.13 24v-8.44H7.08v-3.49h3.05V9.41c0-3.02 1.79-4.69 4.53-4.69 1.31 0 2.69.24 2.69.24v2.96h-1.51c-1.49 0-1.96.93-1.96 1.89v2.26h3.33l-.53 3.49h-2.8V24C19.61 23.1 24 18.1 24 12.07Z" />
    </svg>
  );
}

function XIcon() {
  return (
    <svg {...ICON_PROPS}>
      <path d="M17.53 3h3.06l-6.69 7.64L21.75 21h-6.16l-4.82-6.3L5.25 21H2.18l7.15-8.17L2.25 3h6.32l4.36 5.76L17.53 3Zm-1.07 16.15h1.7L7.62 4.76h-1.82l10.66 14.39Z" />
    </svg>
  );
}

function WhatsAppIcon() {
  return (
    <svg {...ICON_PROPS}>
      <path d="M12.04 2c-5.5 0-9.96 4.46-9.96 9.96 0 1.76.46 3.48 1.34 5L2 22l5.16-1.35a9.92 9.92 0 0 0 4.88 1.25h.01c5.49 0 9.95-4.46 9.95-9.96A9.9 9.9 0 0 0 19.08 4.9 9.9 9.9 0 0 0 12.04 2Zm0 18.18h-.01a8.26 8.26 0 0 1-4.21-1.15l-.3-.18-3.13.82.84-3.06-.2-.31a8.24 8.24 0 0 1-1.26-4.39c0-4.56 3.71-8.27 8.28-8.27 2.21 0 4.29.86 5.85 2.43a8.22 8.22 0 0 1 2.42 5.85c0 4.57-3.71 8.26-8.28 8.26Zm4.54-6.19c-.25-.13-1.47-.72-1.7-.81-.23-.08-.4-.12-.56.13-.17.24-.64.8-.79.97-.14.16-.29.18-.54.06-.25-.13-1.05-.39-2-1.23-.74-.66-1.24-1.47-1.38-1.72-.15-.25-.02-.38.11-.5.11-.11.25-.29.37-.44.13-.14.17-.24.25-.41.09-.16.04-.31-.02-.43-.06-.13-.56-1.35-.77-1.84-.2-.49-.4-.42-.55-.43h-.47c-.16 0-.43.06-.65.31-.22.24-.85.83-.85 2.03 0 1.19.87 2.35.99 2.51.12.16 1.71 2.61 4.14 3.66.58.25 1.03.4 1.38.51.58.19 1.11.16 1.53.1.47-.07 1.47-.6 1.67-1.18.21-.58.21-1.07.15-1.18-.06-.11-.23-.17-.48-.29Z" />
    </svg>
  );
}

interface SocialLink {
  href: string;
  label: string;
  icon: ComponentType;
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
