"use client";

import { useCallback, useEffect, useRef, useState, type ChangeEvent, type FormEvent } from "react";
import Link from "next/link";
import { Card, Checkbox, Label, ListBox, ProgressBar, Select, buttonVariants, cn } from "@heroui/react";
import Button from "@/components/Button";
import CardLabelFields, { labelChanges, labelsOf, type CardLabels } from "@/components/CardLabelFields";
import CropAdjustStep from "@/components/CropAdjustStep";
import ErrorState from "@/components/ErrorState";
import OutOfChecksPanel from "@/components/OutOfChecksPanel";
import Skeleton from "@/components/Skeleton";
import { useAuth } from "@/lib/auth-context";
import { useLocale, useTranslations } from "@/lib/i18n/context";
import { useQuota } from "@/lib/quota-context";
import { toastError, toastSuccess } from "@/lib/toast";
import * as api from "@/lib/api";

const LAST_GAME_KEY = "zgrader_last_game";

/** Wrapped: storage can be absent or throw (private windows, blocked site
 *  data, thumbnail capture). The page works without it. */
function readLastGame(): string | null {
  try {
    return window.localStorage.getItem(LAST_GAME_KEY);
  } catch {
    return null;
  }
}

function rememberGame(game: string): void {
  try {
    window.localStorage.setItem(LAST_GAME_KEY, game);
  } catch {
    // A per-browser convenience; losing it costs one extra tap.
  }
}

function FoilCheckbox({ value, onChange }: { value: boolean; onChange: (next: boolean) => void }) {
  const t = useTranslations();
  return (
    <div className="flex flex-col gap-1">
      <Checkbox.Root isSelected={value} onChange={onChange}>
        <Checkbox.Content>
          <Checkbox.Control>
            <Checkbox.Indicator />
          </Checkbox.Control>
          {t.checkFlow.foil}
        </Checkbox.Content>
      </Checkbox.Root>
      <p className="text-xs text-muted">{t.checkFlow.foilHint}</p>
    </div>
  );
}

/** "Uses one check, only if we can score it." The number comes from the
 *  quota, never the copy; nothing is shown for unlimited plans, an unknown
 *  quota, or a submission already charged. */
function QuotaLine({ charged }: { charged: boolean }) {
  const { quota } = useQuota();
  const t = useTranslations();
  if (charged || !quota || quota.unlimited || quota.remaining === null) return null;
  return (
    <p className="text-xs text-muted">{t.checkFlow.usesOneCheck.replace("{count}", String(quota.remaining))}</p>
  );
}

function VerifyEmailPanel({ email }: { email: string }) {
  const t = useTranslations();
  const [sending, setSending] = useState(false);

  async function resend() {
    setSending(true);
    try {
      await api.resendVerification(email);
      toastSuccess(t.checkFlow.resent);
    } catch (err) {
      toastError(err instanceof api.ApiError ? err.message : t.checkFlow.createFailed);
    } finally {
      setSending(false);
    }
  }

  return (
    <Card className="mx-auto w-full max-w-2xl">
      <Card.Header>
        <Card.Title>{t.checkFlow.unverifiedTitle}</Card.Title>
        <Card.Description>{t.checkFlow.unverifiedBody.replace("{email}", email)}</Card.Description>
      </Card.Header>
      <Card.Content>
        <Button variant="primary" onPress={resend} isDisabled={sending}>
          {t.checkFlow.resend}
        </Button>
      </Card.Content>
    </Card>
  );
}

function DraftsFullPanel() {
  const t = useTranslations();
  return (
    <Card className="mx-auto w-full max-w-2xl">
      <Card.Header>
        <Card.Title>{t.checkFlow.draftsFullTitle}</Card.Title>
        <Card.Description>{t.checkFlow.draftsFullBody}</Card.Description>
      </Card.Header>
      <Card.Content>
        <Link href="/dashboard" className={cn(buttonVariants({ variant: "primary" }), "btn-press btn-neon-hover")}>
          {t.checkFlow.draftsFullLink}
        </Link>
      </Card.Content>
    </Card>
  );
}

function GameSelect({
  games,
  value,
  onChange,
  isDisabled,
}: {
  games: api.Game[];
  value: string;
  onChange: (game: string) => void;
  isDisabled: boolean;
}) {
  const t = useTranslations();
  return (
    <Select.Root
      selectedKey={value}
      onSelectionChange={(key) => onChange(String(key))}
      isDisabled={isDisabled}
      isRequired
      fullWidth
    >
      <Label>{t.checkFlow.game}</Label>
      <Select.Trigger>
        <Select.Value />
        <Select.Indicator />
      </Select.Trigger>
      <Select.Popover>
        <ListBox>
          {games.map((g) => (
            <ListBox.Item id={g.game} key={g.game} textValue={g.game}>
              {g.game}
              {!g.verified ? t.checkFlow.dimensionsUnverified : ""}
            </ListBox.Item>
          ))}
        </ListBox>
      </Select.Popover>
    </Select.Root>
  );
}

/**
 * The photo-first check (spec §5.2): blocks first, then game and photo, then
 * the crop editor in place. Analysis needs only the game (for the card's
 * physical size) and foil; name, set and number are optional labels.
 */
export default function CheckFlow({
  submission,
  onChange,
}: {
  submission: api.SubmissionDetail | null;
  onChange: (next: api.SubmissionDetail) => void;
}) {
  const { user, token } = useAuth();
  const { quota, refresh: refreshQuota } = useQuota();
  const { locale } = useLocale();
  const t = useTranslations();
  const cameraRef = useRef<HTMLInputElement>(null);
  const libraryRef = useRef<HTMLInputElement>(null);

  const [games, setGames] = useState<api.Game[] | null>(null);
  const [gamesError, setGamesError] = useState<string | null>(null);
  const [game, setGame] = useState(submission?.card?.game ?? "");
  const [uploading, setUploading] = useState(false);
  const [mailIn, setMailIn] = useState(false);
  const [draftsFull, setDraftsFull] = useState(false);
  const [exhausted, setExhausted] = useState(false);
  const [foil, setFoil] = useState(submission?.card?.foil ?? false);
  const [labels, setLabels] = useState<CardLabels>(() => labelsOf(submission?.card ?? null));

  const loadGames = useCallback(() => {
    setGamesError(null);
    api
      .getGames()
      .then((list) => {
        setGames(list);
        // A draft already has its game; only a fresh check picks a default.
        if (!submission) {
          const last = readLastGame();
          setGame(last && list.some((g) => g.game === last) ? last : list[0]?.game ?? "");
        }
      })
      .catch((err) => setGamesError(err instanceof Error ? err.message : t.checkFlow.createFailed));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // loadGames clears gamesError synchronously before its async request --
  // exactly the "reset state, then reload" shape this rule exists to flag in
  // general, and exactly what this effect is for.
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(loadGames, [loadGames]);

  /** The two refusals the page shows as panels rather than toasts. */
  function handleRefusal(err: unknown): boolean {
    if (!(err instanceof api.ApiError)) return false;
    if (err.status === 402) {
      setExhausted(true);
      void refreshQuota();
      return true;
    }
    if (api.errorCode(err) === "too_many_drafts") {
      setDraftsFull(true);
      return true;
    }
    return false;
  }

  /** The draft becomes this page's address without a remount, so a reload
   *  resumes it rather than starting another. */
  function adopt(created: api.SubmissionDetail) {
    rememberGame(game);
    window.history.replaceState(null, "", `/dashboard/${created.submission_code}`);
    onChange(created);
  }

  async function handleFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file || !token) return;
    setUploading(true);
    try {
      let current = submission;
      if (!current) {
        current = await api.createSubmission(token, { game, foil: false, language: locale });
        // Adopted before the upload, so a failed upload retries into this
        // draft rather than opening a second one.
        adopt(current);
      }
      onChange(await api.uploadScan(token, current.submission_code, "front", file));
    } catch (err) {
      if (!handleRefusal(err)) {
        toastError(err instanceof api.ApiError ? err.message : t.upload.uploadFailed);
      }
    } finally {
      setUploading(false);
    }
  }

  async function handleMailIn(event: FormEvent) {
    event.preventDefault();
    if (!token) return;
    setUploading(true);
    try {
      adopt(
        await api.createSubmission(token, {
          game,
          card_name: labels.card_name.trim(),
          set_name: labels.set_name.trim() || undefined,
          card_number: labels.card_number.trim() || undefined,
          foil,
          language: locale,
          mail_in: true,
        })
      );
    } catch (err) {
      if (!handleRefusal(err)) {
        toastError(err instanceof api.ApiError ? err.message : t.checkFlow.createFailed);
      }
    } finally {
      setUploading(false);
    }
  }

  /** Runs before the crop check: foil changes the analysis, so it has to be
   *  saved before the analysis runs; labels ride along. */
  async function saveCardDetails(): Promise<boolean> {
    if (!token || !submission) return false;
    const changes = labelChanges(labelsOf(submission.card), labels);
    if (foil !== (submission.card?.foil ?? false)) changes.foil = foil;
    if (Object.keys(changes).length === 0) return true;
    try {
      onChange(await api.updateCard(token, submission.submission_code, changes));
      return true;
    } catch (err) {
      toastError(err instanceof api.ApiError ? err.message : t.checkFlow.detailsFailed);
      return false;
    }
  }

  const outOfChecks =
    exhausted || (quota !== null && !quota.unlimited && quota.remaining === 0 && !submission?.charged);

  if (user && !user.is_verified) return <VerifyEmailPanel email={user.email} />;
  if (outOfChecks) return <OutOfChecksPanel />;
  if (draftsFull) return <DraftsFullPanel />;

  if (submission && token && submission.scan_sides.includes("front")) {
    return (
      <div className="mx-auto w-full max-w-2xl">
        <CropAdjustStep
          token={token}
          code={submission.submission_code}
          side="front"
          confirmLabel={t.checkFlow.analyse}
          beforeConfirm={saveCardDetails}
          onConfirmError={handleRefusal}
          onConfirmed={(updated) => {
            onChange(updated);
            void refreshQuota();
          }}
        >
          <FoilCheckbox value={foil} onChange={setFoil} />
          <details className="rounded-lg border border-border px-3 py-2">
            <summary className="-my-2 cursor-pointer py-2 text-sm font-semibold text-foreground">
              {t.checkFlow.detailsSummary}
            </summary>
            <div className="mt-2 flex flex-col gap-3 pb-1">
              <CardLabelFields value={labels} onChange={setLabels} />
            </div>
          </details>
          <QuotaLine charged={submission.charged} />
        </CropAdjustStep>
      </div>
    );
  }

  return (
    <Card className="mx-auto w-full max-w-2xl">
      <Card.Header>
        <Card.Title>{mailIn ? t.checkFlow.mailInTitle : t.checkFlow.title}</Card.Title>
        <Card.Description>{mailIn ? t.checkFlow.mailInBody : t.checkFlow.subtitle}</Card.Description>
      </Card.Header>
      <Card.Content className="flex flex-col gap-4">
        {gamesError ? (
          <ErrorState message={gamesError} onRetry={loadGames} retryLabel={t.common.retry} />
        ) : games === null ? (
          <Skeleton className="h-10 w-full" />
        ) : (
          <GameSelect games={games} value={game} onChange={setGame} isDisabled={submission !== null} />
        )}

        {mailIn ? (
          <form className="flex flex-col gap-4" onSubmit={handleMailIn}>
            <CardLabelFields value={labels} onChange={setLabels} nameRequired />
            <FoilCheckbox value={foil} onChange={setFoil} />
            <Button
              type="submit"
              variant="primary"
              isDisabled={uploading || !game || !labels.card_name.trim()}
              fullWidth
            >
              {t.checkFlow.mailInSubmit}
            </Button>
            <button
              type="button"
              onClick={() => setMailIn(false)}
              className="-my-2 self-start py-2 text-sm text-accent hover:underline"
            >
              {t.checkFlow.mailInCancel}
            </button>
          </form>
        ) : (
          <>
            <p className="text-sm text-muted">{t.upload.backgroundHint}</p>
            {uploading ? (
              <ProgressBar aria-label={t.upload.uploading} isIndeterminate className="w-full">
                <ProgressBar.Track>
                  <ProgressBar.Fill />
                </ProgressBar.Track>
              </ProgressBar>
            ) : (
              <div className="grid gap-2 sm:grid-cols-2">
                {/* Two inputs on purpose: a bare `capture` opens the camera
                    directly on Android, with no way to pick a photo already
                    taken. */}
                <input ref={cameraRef} type="file" accept="image/*" capture="environment" onChange={handleFile} className="hidden" />
                <input ref={libraryRef} type="file" accept="image/*" onChange={handleFile} className="hidden" />
                <Button variant="primary" onPress={() => cameraRef.current?.click()} isDisabled={!game}>
                  {t.checkFlow.takePhoto}
                </Button>
                <Button variant="outline" onPress={() => libraryRef.current?.click()} isDisabled={!game}>
                  {t.checkFlow.choosePhoto}
                </Button>
              </div>
            )}
            <QuotaLine charged={submission?.charged ?? false} />
            {!submission && (
              <button
                type="button"
                onClick={() => setMailIn(true)}
                className="-my-2 self-start py-2 text-sm text-accent hover:underline"
              >
                {t.checkFlow.mailInLink}
              </button>
            )}
          </>
        )}
      </Card.Content>
    </Card>
  );
}
