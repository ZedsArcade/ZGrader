"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import Button from "@/components/Button";
import { useAuth } from "@/lib/auth-context";
import { useBranding } from "@/lib/branding-context";
import { useTranslations } from "@/lib/i18n/context";
import { CARE_PREFIX } from "@/lib/brand";
import { useBrand } from "@/lib/use-brand";
import BrandLogo from "@/components/BrandLogo";
import BrandSwitch from "@/components/brand-switch";
import QuotaChip from "@/components/QuotaChip";
import ThemeSwitch from "@/components/theme-switch";
import LocaleSwitch from "@/components/locale-switch";
import NavDrawer from "@/components/nav-drawer";

const DESKTOP_LINK_CLASS =
  "text-sm font-medium text-foreground hover:text-accent link-accent-hover";
const DRAWER_LINK_CLASS =
  "rounded-lg px-3 py-2 text-sm font-medium text-foreground hover:bg-surface-hover";

export default function NavBar() {
  const { user, logout, loading } = useAuth();
  const t = useTranslations();
  const router = useRouter();
  const brand = useBrand();

  function handleLogout() {
    logout();
    router.push("/");
  }

  // Public links, shown whether or not anyone is signed in. The desktop bar
  // only takes the first two: it already carries up to five children when
  // authed, and the full set would break the layout at md widths. The drawer
  // has the room for all of them, and the footer carries everything anyway.
  const publicLinks = [
    { href: "/about", label: t.nav.about },
    // Each brand has its own services page; the link follows whichever
    // section you are in rather than always landing on the analysis one.
    { href: brand === "care" ? `${CARE_PREFIX}/services` : "/services", label: t.nav.services },
    { href: "/how-it-works", label: t.nav.howItWorks },
    { href: "/methodology", label: t.nav.methodology },
    { href: "/contact", label: t.nav.contact },
  ];
  const desktopLinks = publicLinks.slice(0, 2);

  return (
    <header className="sticky top-0 z-40 border-b border-border bg-surface/90 backdrop-blur">
      {/* gap-4 so the left group can never butt against the first nav link --
          justify-between alone lets them touch once the bar is full. */}
      <div className="mx-auto flex h-16 w-full max-w-5xl items-center justify-between gap-4 px-5">
        {/* The switch is the identity. A text wordmark used to sit here too,
            but it repeated whichever button was already highlighted, wrapped
            onto two lines, and cost ~130px the navigation needed. An operator
            logo takes that slot instead, and renders only if one is set. */}
        {/* `min-w-0` is what stops the bar pushing the whole page sideways.
            Both brand names come from Settings, so their combined width is
            operator-controlled and unbounded -- without this the switch sets a
            floor on the header's width and every page scrolls horizontally on
            a phone. With it, the switch is the one element that gives, and it
            truncates instead (see BrandSwitch).

            `md:min-w-max` puts that floor back once the desktop nav appears.
            There the nav is the wide element, and letting the brand group
            shrink for it clipped the brand name by a few pixels at 1280px --
            a regression, not a fix. The overflow only ever happened on
            mobile, so the shrink belongs there too. */}
        <div className="flex min-w-0 items-center gap-3 md:min-w-max">
          <BrandLogo />
          <BrandSwitch />
        </div>

        <nav className="hidden items-center gap-6 md:flex">
          {desktopLinks.map(({ href, label }) => (
            <Link key={href} href={href} className={DESKTOP_LINK_CLASS}>
              {label}
            </Link>
          ))}
          {loading ? null : user ? (
            <>
              {user.role === "operator" ? (
                <Link href="/admin" className={DESKTOP_LINK_CLASS}>
                  {t.nav.admin}
                </Link>
              ) : (
                <Link href="/dashboard" className={DESKTOP_LINK_CLASS}>
                  {t.nav.dashboard}
                </Link>
              )}
              {/* The address doubles as the account link -- the bar is already
                  at its width budget and a separate "Account" item wouldn't fit. */}
              <Link
                href="/account"
                aria-label={t.nav.account}
                className="text-sm text-muted hover:text-accent link-accent-hover"
              >
                {user.email}
              </Link>
              <QuotaChip />
              <LocaleSwitch />
              <ThemeSwitch />
              <Button variant="outline" size="sm" onPress={handleLogout}>
                {t.nav.logout}
              </Button>
            </>
          ) : (
            <>
              <Link href="/login" className={DESKTOP_LINK_CLASS}>
                {t.nav.login}
              </Link>
              <Link href="/register" className={DESKTOP_LINK_CLASS}>
                {t.nav.register}
              </Link>
              <LocaleSwitch />
              <ThemeSwitch />
            </>
          )}
        </nav>

        {/* `shrink-0`: these are fixed-size icon controls, so they must hold
            their size and let the brand switch absorb the shortfall.

            The quota chip and locale switch used to sit here too and were the
            difference between fitting and not -- three text controls plus a
            brand switch cannot share 375px. They moved into the drawer, which
            has room for them and is one tap away. */}
        <div className="flex shrink-0 items-center gap-2 md:hidden">
          <ThemeSwitch />
          <NavDrawer>
            {(close) => (
              <>
                {publicLinks.map(({ href, label }) => (
                  <Link key={href} href={href} onClick={close} className={DRAWER_LINK_CLASS}>
                    {label}
                  </Link>
                ))}
                <hr className="mx-3 my-2 border-border" />
                {loading ? null : user ? (
                  <>
                    {user.role === "operator" ? (
                      <Link href="/admin" onClick={close} className={DRAWER_LINK_CLASS}>
                        {t.nav.admin}
                      </Link>
                    ) : (
                      <Link href="/dashboard" onClick={close} className={DRAWER_LINK_CLASS}>
                        {t.nav.dashboard}
                      </Link>
                    )}
                    <Link href="/account" onClick={close} className={DRAWER_LINK_CLASS}>
                      {t.nav.account}
                    </Link>
                    <div className="px-3 py-2 text-xs text-muted">{user.email}</div>
                    <Button
                      variant="outline"
                      size="sm"
                      className="mx-3 mt-2"
                      onPress={() => {
                        close();
                        handleLogout();
                      }}
                    >
                      {t.nav.logout}
                    </Button>
                  </>
                ) : (
                  <>
                    <Link href="/login" onClick={close} className={DRAWER_LINK_CLASS}>
                      {t.nav.login}
                    </Link>
                    <Link href="/register" onClick={close} className={DRAWER_LINK_CLASS}>
                      {t.nav.register}
                    </Link>
                  </>
                )}
                <hr className="mx-3 my-2 border-border" />
                {/* Relocated from the bar, where they did not fit. The chip is
                    a link to /services, so it closes the drawer on the way --
                    a drawer left open over the page it just navigated to reads
                    as a broken tap. */}
                <div className="flex items-center justify-between gap-3 px-3 py-2">
                  <LocaleSwitch />
                  <span onClick={close}>
                    <QuotaChip />
                  </span>
                </div>
              </>
            )}
          </NavDrawer>
        </div>
      </div>
    </header>
  );
}
