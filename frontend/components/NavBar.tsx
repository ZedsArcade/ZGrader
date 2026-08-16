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

  // Public links, shown whether or not anyone is signed in. How many the
  // desktop bar can take depends on who is looking: signed in it also carries
  // the dashboard, the email address, the quota chip and a logout button.
  // Signed out there is room for one more, and pricing is worth the slot.
  // The drawer carries all of them below lg, and the footer always does.
  const publicLinks = [
    { href: "/about", label: t.nav.about },
    // Each brand has its own services page; the link follows whichever
    // section you are in rather than always landing on the analysis one.
    { href: brand === "care" ? `${CARE_PREFIX}/services` : "/services", label: t.nav.services },
    // Shared between both brands, like /about: what a check costs does not
    // change with the section you arrived through, so there is one page and it
    // simply keeps whichever palette is active.
    { href: "/pricing", label: t.nav.pricing },
    { href: "/how-it-works", label: t.nav.howItWorks },
    { href: "/methodology", label: t.nav.methodology },
    { href: "/contact", label: t.nav.contact },
  ];
  const desktopLinks = publicLinks.slice(0, user ? 2 : 3);

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

            `lg:min-w-max` puts that floor back once the desktop nav appears.
            There the nav is the wide element, and letting the brand group
            shrink for it clipped the brand name by a few pixels at 1280px --
            a regression, not a fix. The overflow only ever happened on
            mobile, so the shrink belongs there too. Pinned to the same
            breakpoint the nav uses, so the two cannot drift apart. */}
        <div className="flex min-w-0 items-center gap-3 lg:min-w-max">
          <BrandLogo />
          <BrandSwitch />
        </div>

        {/* `lg`, not `md`. The authed bar measures ~844px on its own, so with
            the brand group and the padding it needs about 1114px before it
            fits -- it was appearing at 768 and overflowing every viewport from
            there to roughly 1150. Signed out it was subtler and Spanish-only:
            "Nosotros"/"Iniciar sesión"/"Registrarse" are longer than their
            English counterparts, which is why an English sweep at 768 passed.
            Below lg the drawer carries everything, which it already did. */}
        <nav className="hidden items-center gap-5 lg:flex">
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
                  at its width budget and a separate "Account" item wouldn't fit.

                  Bounded, because it is the one element here whose width nobody
                  controls: a customer chooses their own address, and a long one
                  measured 245px of an 844px bar. Truncating caps the single
                  unbounded contributor rather than leaving the layout to hope.
                  `title` keeps the whole address available on hover, and
                  `aria-label` already names the destination for a screen
                  reader, so the ellipsis costs nothing but pixels. */}
              <Link
                href="/account"
                aria-label={t.nav.account}
                title={user.email}
                className="max-w-[15ch] truncate text-sm text-muted hover:text-accent link-accent-hover"
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
        <div className="flex shrink-0 items-center gap-2 lg:hidden">
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
