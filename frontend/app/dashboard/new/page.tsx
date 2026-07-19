"use client";

import { useEffect, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import {
  Button,
  Card,
  Checkbox,
  Input,
  Label,
  ListBox,
  Select,
  TextField,
} from "@heroui/react";
import RequireAuth from "@/components/RequireAuth";
import { useAuth } from "@/lib/auth-context";
import { toastError } from "@/lib/toast";
import * as api from "@/lib/api";

function NewSubmissionForm() {
  const { token } = useAuth();
  const router = useRouter();
  const [games, setGames] = useState<api.Game[]>([]);
  const [game, setGame] = useState("");
  const [cardName, setCardName] = useState("");
  const [setName, setSetName] = useState("");
  const [cardNumber, setCardNumber] = useState("");
  const [foil, setFoil] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    api.getGames().then((list) => {
      setGames(list);
      if (list.length > 0) setGame(list[0].game);
    });
  }, []);

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
      });
      router.push(`/dashboard/${submission.submission_code}`);
    } catch (err) {
      toastError(err instanceof Error ? err.message : "Failed to create submission");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Card className="mx-auto max-w-xl">
      <Card.Header>
        <Card.Title>New submission</Card.Title>
        <Card.Description>Tell us about the card, then ship it to us for scanning.</Card.Description>
      </Card.Header>
      <Card.Content>
        <form className="flex flex-col gap-4" onSubmit={handleSubmit}>
          <Select.Root
            selectedKey={game}
            onSelectionChange={(key) => setGame(String(key))}
            isRequired
            fullWidth
          >
            <Label>Game</Label>
            <Select.Trigger>
              <Select.Value />
              <Select.Indicator />
            </Select.Trigger>
            <Select.Popover>
              <ListBox>
                {games.map((g) => (
                  <ListBox.Item id={g.game} key={g.game} textValue={g.game}>
                    {g.game}
                    {!g.verified ? " (dimensions unverified)" : ""}
                  </ListBox.Item>
                ))}
              </ListBox>
            </Select.Popover>
          </Select.Root>

          <TextField value={cardName} onChange={setCardName} isRequired fullWidth>
            <Label>Card name</Label>
            <Input />
          </TextField>

          <TextField value={setName} onChange={setSetName} fullWidth>
            <Label>Set (optional)</Label>
            <Input />
          </TextField>

          <TextField value={cardNumber} onChange={setCardNumber} fullWidth>
            <Label>Card number (optional)</Label>
            <Input />
          </TextField>

          <Checkbox.Root isSelected={foil} onChange={setFoil}>
            <Checkbox.Content>
              <Checkbox.Control>
                <Checkbox.Indicator />
              </Checkbox.Control>
              Foil / holo
            </Checkbox.Content>
          </Checkbox.Root>

          <Button type="submit" variant="primary" isDisabled={submitting || !game} fullWidth>
            {submitting ? "Creating…" : "Create submission"}
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
