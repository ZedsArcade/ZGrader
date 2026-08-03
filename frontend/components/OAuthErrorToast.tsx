"use client";

import { useEffect } from "react";
import { useSearchParams } from "next/navigation";
import { toastError } from "@/lib/toast";
import { useTranslations } from "@/lib/i18n/context";

/**
 * Surfaces the reason a Google sign-in bounced back -- most often the address
 * already having a password account, which is refused rather than linked.
 *
 * Split into its own component purely so the `useSearchParams` call can sit
 * inside a Suspense boundary at the call site. Reading search params opts a
 * route out of static prerendering unless it is suspended, and the sign-in
 * pages are prerendered; isolating it here keeps that boundary as small as
 * the one hook rather than wrapping the whole form.
 */
export default function OAuthErrorToast() {
  const searchParams = useSearchParams();
  const t = useTranslations();
  const oauthError = searchParams?.get("oauth_error");

  useEffect(() => {
    if (oauthError) toastError(`${t.googleAuth.errorPrefix} ${oauthError}`);
  }, [oauthError, t]);

  return null;
}
