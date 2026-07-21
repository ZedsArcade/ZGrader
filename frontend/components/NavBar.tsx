"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { Button } from "@heroui/react";
import { useAuth } from "@/lib/auth-context";
import { useBranding } from "@/lib/branding-context";
import { useTranslations } from "@/lib/i18n/context";
import ThemeSwitch from "@/components/theme-switch";
import LocaleSwitch from "@/components/locale-switch";
import NavDrawer from "@/components/nav-drawer";

export default function NavBar() {
  const { user, logout, loading } = useAuth();
  const { business_name } = useBranding();
  const t = useTranslations();
  const router = useRouter();

  function handleLogout() {
    logout();
    router.push("/");
  }

  return (
    <header className="sticky top-0 z-40 border-b border-border bg-surface/90 backdrop-blur">
      <div className="mx-auto flex h-16 w-full max-w-5xl items-center justify-between px-5">
        <Link href="/" className="text-base font-semibold text-foreground">
          {business_name}
        </Link>

        <nav className="hidden items-center gap-6 md:flex">
          {loading ? null : user ? (
            <>
              {user.role === "operator" ? (
                <Link href="/admin" className="text-sm font-medium text-foreground hover:text-accent">
                  {t.nav.admin}
                </Link>
              ) : (
                <Link href="/dashboard" className="text-sm font-medium text-foreground hover:text-accent">
                  {t.nav.dashboard}
                </Link>
              )}
              <span className="text-sm text-muted">{user.email}</span>
              <LocaleSwitch />
              <ThemeSwitch />
              <Button variant="outline" size="sm" onPress={handleLogout}>
                {t.nav.logout}
              </Button>
            </>
          ) : (
            <>
              <Link href="/login" className="text-sm font-medium text-foreground hover:text-accent">
                {t.nav.login}
              </Link>
              <Link href="/register" className="text-sm font-medium text-foreground hover:text-accent">
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
                {loading ? null : user ? (
                  <>
                    {user.role === "operator" ? (
                      <Link
                        href="/admin"
                        onClick={close}
                        className="rounded-lg px-3 py-2 text-sm font-medium text-foreground hover:bg-surface-hover"
                      >
                        {t.nav.admin}
                      </Link>
                    ) : (
                      <Link
                        href="/dashboard"
                        onClick={close}
                        className="rounded-lg px-3 py-2 text-sm font-medium text-foreground hover:bg-surface-hover"
                      >
                        {t.nav.dashboard}
                      </Link>
                    )}
                    <div className="px-3 py-2 text-sm text-muted">{user.email}</div>
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
                    <Link
                      href="/login"
                      onClick={close}
                      className="rounded-lg px-3 py-2 text-sm font-medium text-foreground hover:bg-surface-hover"
                    >
                      {t.nav.login}
                    </Link>
                    <Link
                      href="/register"
                      onClick={close}
                      className="rounded-lg px-3 py-2 text-sm font-medium text-foreground hover:bg-surface-hover"
                    >
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
