"use client";

import { useCallback, useEffect, useState } from "react";
import { Card } from "@heroui/react";
import Button from "@/components/Button";
import * as api from "@/lib/api";
import { useTranslations } from "@/lib/i18n/context";
import { toastError } from "@/lib/toast";

/**
 * The customer's control over their own share link.
 *
 * Fetched separately from the submission because the token is a secret: it has
 * no business riding along on every read of every submission, only on the one
 * screen that shows it.
 *
 * Three states, and the middle one is the point. Off is the default and where
 * every submission starts; on shows the link and offers to replace it; and
 * "not yet" is what an unpublished report gets, because the backend refuses to
 * share one and a button that always 409s is worse than no button.
 */
export default function SharePanel({
  code,
  token,
  publishable,
}: {
  code: string;
  token: string;
  /** Whether the report is published. Mirrors the backend's own gate rather
   *  than replacing it -- the server still refuses, this just stops offering. */
  publishable: boolean;
}) {
  const t = useTranslations();
  const [state, setState] = useState<api.ShareState | null>(null);
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);

  const load = useCallback(() => {
    api
      .getShareState(token, code)
      .then(setState)
      // Silent: this is a secondary control on a page that has already loaded.
      // Failing it loudly would put an error banner over a working report.
      .catch(() => setState(null));
  }, [token, code]);

  useEffect(load, [load]);

  async function run(action: () => Promise<api.ShareState | void>) {
    setBusy(true);
    setCopied(false);
    try {
      const next = await action();
      setState(next ?? { enabled: false, url: null, enabled_at: null });
    } catch (err) {
      toastError(err instanceof Error ? err.message : t.submissionDetail.shareFailed);
    } finally {
      setBusy(false);
    }
  }

  async function copy() {
    if (!state?.url) return;
    try {
      await navigator.clipboard.writeText(state.url);
      setCopied(true);
    } catch {
      // Clipboard access can be refused; the link is on screen and selectable,
      // so there is nothing to recover from.
    }
  }

  return (
    <Card>
      <Card.Header>
        <Card.Title>{t.submissionDetail.shareTitle}</Card.Title>
      </Card.Header>
      <Card.Content className="flex flex-col gap-3">
        <p className="text-sm text-muted">{t.submissionDetail.shareBody}</p>

        {!publishable ? (
          <p className="text-sm text-muted">{t.submissionDetail.shareUnavailable}</p>
        ) : state?.enabled && state.url ? (
          <>
            {/* break-all, because a token is an unbroken 22-character string
                and the page must not scroll sideways on a phone. */}
            <code className="block break-all rounded-lg border border-border bg-surface-secondary p-2 text-xs text-foreground">
              {state.url}
            </code>
            <div className="flex flex-wrap gap-2">
              <Button variant="primary" onPress={copy}>
                {copied ? t.submissionDetail.shareCopied : t.submissionDetail.shareCopy}
              </Button>
              <Button
                variant="outline"
                isDisabled={busy}
                onPress={() => run(() => api.rotateShare(token, code))}
              >
                {t.submissionDetail.shareRotate}
              </Button>
              <Button
                variant="outline"
                isDisabled={busy}
                onPress={() => run(() => api.disableShare(token, code))}
              >
                {t.submissionDetail.shareDisable}
              </Button>
            </div>
            <p className="text-xs text-muted">{t.submissionDetail.shareRotateBody}</p>
          </>
        ) : (
          <>
            <p className="text-xs text-muted">{t.submissionDetail.shareDisabledNote}</p>
            <div>
              <Button
                variant="primary"
                isDisabled={busy}
                onPress={() => run(() => api.enableShare(token, code))}
              >
                {busy ? t.submissionDetail.shareEnabling : t.submissionDetail.shareEnable}
              </Button>
            </div>
          </>
        )}
      </Card.Content>
    </Card>
  );
}
