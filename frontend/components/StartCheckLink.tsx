"use client";

import Link from "next/link";
import type { ComponentProps, ReactNode } from "react";
import { useAuth } from "@/lib/auth-context";

/**
 * The "start a free check" call to action, pointed at wherever the visitor
 * actually needs to go.
 *
 * Signed out, that is the registration page. Signed in, it is the dashboard --
 * sending someone who already has an account to a form asking them to create
 * one reads as the site not knowing who they are, and the thing they came to
 * do (start a submission) is one click further away than before they logged
 * in.
 *
 * `href` stays a real link rather than a click handler so middle-click,
 * Cmd-click and "copy link address" all behave, and so it still resolves
 * without JavaScript.
 *
 * There is a brief window on first paint where `loading` is true and `user` is
 * still null, during which this points at /register. That is not left to
 * chance: app/register/page.tsx redirects an authenticated visitor to the
 * dashboard, which closes the race here and also covers someone typing
 * /register directly.
 */
export default function StartCheckLink({
  children,
  ...props
}: { children: ReactNode } & Omit<ComponentProps<typeof Link>, "href">) {
  const { user } = useAuth();
  return (
    <Link href={user ? "/dashboard" : "/register"} {...props}>
      {children}
    </Link>
  );
}
