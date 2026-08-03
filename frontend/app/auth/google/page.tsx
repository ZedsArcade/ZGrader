"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Card } from "@heroui/react";
import { useAuth } from "@/lib/auth-context";
import { useTranslations } from "@/lib/i18n/context";

/**
 * Landing point for the Google sign-in redirect.
 *
 * The backend sends the session token in the URL *fragment* rather than the
 * query string. A fragment is never transmitted to a server, so the token
 * stays out of access logs, proxy logs and the Referer header. The tradeoff
 * is that only the browser can read it, which is why this page exists at all
 * rather than the backend handing the token straight to the app.
 *
 * The fragment is cleared as soon as it has been read, so the token does not
 * linger in the address bar or in browser history.
 */
export default function GoogleCallbackPage() {
  const router = useRouter();
  const { adoptToken } = useAuth();
  const t = useTranslations();
  const [error, setError] = useState<string | null>(null);
  // React runs effects twice in development's strict mode; adopting the same
  // token twice is harmless but the second run finds the fragment already
  // cleared and would show a spurious error.
  const handled = useRef(false);

  useEffect(() => {
    if (handled.current) return;
    handled.current = true;

    const params = new URLSearchParams(window.location.hash.replace(/^#/, ""));
    const token = params.get("token");
    const next = params.get("next") || "/dashboard";

    // Clear it before anything can go wrong below, so a failure can't leave
    // a live token sitting in the address bar.
    window.history.replaceState(null, "", window.location.pathname);

    if (!token) {
      setError(t.googleAuth.missingToken);
      return;
    }

    adoptToken(token)
      .then(() => router.replace(next.startsWith("/") ? next : "/dashboard"))
      .catch(() => setError(t.googleAuth.failed));
  }, [adoptToken, router, t]);

  return (
    <Card className="mx-auto max-w-md">
      <Card.Header>
        <Card.Title>{error ? t.googleAuth.problemTitle : t.googleAuth.signingIn}</Card.Title>
      </Card.Header>
      <Card.Content>
        <p className="text-sm text-muted">{error ?? t.googleAuth.oneMoment}</p>
        {error && (
          <a href="/login" className="mt-4 inline-block text-sm text-accent link-accent-hover">
            {t.googleAuth.backToLogin}
          </a>
        )}
      </Card.Content>
    </Card>
  );
}
