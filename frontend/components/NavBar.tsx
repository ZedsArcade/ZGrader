"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import Button from "@/components/Button";
import { useAuth } from "@/lib/auth-context";
import { useBranding } from "@/lib/branding-context";
import { useTranslations } from "@/lib/i18n/context";
import { titanOne } from "@/lib/fonts";
import ThemeSwitch from "@/components/theme-switch";
import LocaleSwitch from "@/components/locale-switch";
import NavDrawer from "@/components/nav-drawer";

const DESKTOP_LINK_CLASS =
  "text-sm font-medium text-foreground hover:text-accent link-accent-hover";
const DRAWER_LINK_CLASS =
  "rounded-lg px-3 py-2 text-sm font-medium text-foreground hover:bg-surface-hover";

export default function NavBar() {
  const { user, logout, loading } = useAuth();
  const { business_name } = useBranding();
  const t = useTranslations();
  const router = useRouter();

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
    { href: "/services", label: t.nav.services },
    { href: "/how-it-works", label: t.nav.howItWorks },
    { href: "/methodology", label: t.nav.methodology },
    { href: "/contact", label: t.nav.contact },
  ];
  const desktopLinks = publicLinks.slice(0, 2);

  return (
    <header className="sticky top-0 z-40 border-b border-border bg-surface/90 backdrop-blur">
      <div className="mx-auto flex h-16 w-full max-w-5xl items-center justify-between px-5">
        <Link href="/" className={`${titanOne.className} text-xl tracking-wide text-foreground`}>
          {business_name}
        </Link>

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

        <div className="flex items-center gap-2 md:hidden">
          <LocaleSwitch />
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
              </>
            )}
          </NavDrawer>
        </div>
      </div>
    </header>
  );
}
