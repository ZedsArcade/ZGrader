"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import {
  Card,
  Checkbox,
  Input,
  Label,
  ListBox,
  Select,
  TextField,
} from "@heroui/react";
import Button from "@/components/Button";
import RequireAuth from "@/components/RequireAuth";
import Skeleton from "@/components/Skeleton";
import ErrorState from "@/components/ErrorState";
import { useAuth } from "@/lib/auth-context";
import { toastError } from "@/lib/toast";
import { useLocale, useTranslations } from "@/lib/i18n/context";
import * as api from "@/lib/api";

function NewSubmissionForm() {
  const { token } = useAuth();
  const router = useRouter();
  const { locale } = useLocale();
  const t = useTranslations();
  const [games, setGames] = useState<api.Game[] | null>(null);
  const [gamesError, setGamesError] = useState<string | null>(null);
  const [game, setGame] = useState("");
  const [cardName, setCardName] = useState("");
  const [setName, setSetName] = useState("");
  const [cardNumber, setCardNumber] = useState("");
  const [foil, setFoil] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const loadGames = useCallback(() => {
    setGamesError(null);
    api
      .getGames()
      .then((list) => {
        setGames(list);
        if (list.length > 0) setGame(list[0].game);
      })
      .catch((err) => setGamesError(err instanceof Error ? err.message : t.newSubmission.gamesLoadFailed));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(loadGames, [loadGames]);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!token) return;
    setSubmitting(true);
    try {
      const submission = await api.createSubmission(token, {
        game,
        card_name: cardName,
        set_name: setName || undefined,
        card_number: cardNumber || undefined,
        foil,
        language: locale,
      });
      router.push(`/dashboard/${submission.submission_code}`);
    } catch (err) {
      toastError(err instanceof Error ? err.message : t.newSubmission.failed);
    } finally {
      setSubmitting(false);
    }
  }

  if (gamesError) {
    return (
      <div className="mx-auto max-w-xl">
        <ErrorState message={gamesError} onRetry={loadGames} retryLabel={t.common.retry} />
      </div>
    );
  }

  if (games === null) {
    return (
      <Card className="mx-auto max-w-xl">
        <Card.Content className="flex flex-col gap-4">
          <Skeleton className="h-6 w-40" />
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
        </Card.Content>
      </Card>
    );
  }

  return (
    <Card className="mx-auto max-w-xl">
      <Card.Header>
        <Card.Title>{t.newSubmission.title}</Card.Title>
        <Card.Description>{t.newSubmission.subtitle}</Card.Description>
      </Card.Header>
      <Card.Content>
        <form className="flex flex-col gap-4" onSubmit={handleSubmit}>
          <Select.Root
            selectedKey={game}
            onSelectionChange={(key) => setGame(String(key))}
            isRequired
            fullWidth
          >
            <Label>{t.newSubmission.game}</Label>
            <Select.Trigger>
              <Select.Value />
              <Select.Indicator />
            </Select.Trigger>
            <Select.Popover>
              <ListBox>
                {games.map((g) => (
                  <ListBox.Item id={g.game} key={g.game} textValue={g.game}>
                    {g.game}
                    {!g.verified ? t.newSubmission.dimensionsUnverified : ""}
                  </ListBox.Item>
                ))}
              </ListBox>
            </Select.Popover>
          </Select.Root>

          <TextField value={cardName} onChange={setCardName} isRequired fullWidth>
            <Label>{t.newSubmission.cardName}</Label>
            <Input />
          </TextField>

          <TextField value={setName} onChange={setSetName} fullWidth>
            <Label>{t.newSubmission.setName}</Label>
            <Input />
          </TextField>

          <TextField value={cardNumber} onChange={setCardNumber} fullWidth>
            <Label>{t.newSubmission.cardNumber}</Label>
            <Input />
          </TextField>

          <Checkbox.Root isSelected={foil} onChange={setFoil}>
            <Checkbox.Content>
              <Checkbox.Control>
                <Checkbox.Indicator />
              </Checkbox.Control>
              {t.newSubmission.foil}
            </Checkbox.Content>
          </Checkbox.Root>

          <Button type="submit" variant="primary" isDisabled={submitting || !game} fullWidth>
            {submitting ? t.newSubmission.submitting : t.newSubmission.submit}
          </Button>
        </form>
      </Card.Content>
    </Card>
  );
}

export default function NewSubmissionPage() {
  return (
    <RequireAuth>
      <NewSubmissionForm />
    </RequireAuth>
  );
}
