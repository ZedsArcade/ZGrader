"use client";

import { Input, Label, TextField } from "@heroui/react";
import type { Card, CardUpdate } from "@/lib/api";
import { useTranslations } from "@/lib/i18n/context";

/** The card's labels as form state: never null, so inputs stay controlled. */
export type CardLabels = { card_name: string; set_name: string; card_number: string };

export function labelsOf(card: Card | null): CardLabels {
  return {
    card_name: card?.card_name ?? "",
    set_name: card?.set_name ?? "",
    card_number: card?.card_number ?? "",
  };
}

/** Only what changed, as a PATCH .../card body. A blanked field is sent as
 *  null, which clears it. */
export function labelChanges(before: CardLabels, after: CardLabels): CardUpdate {
  const changes: CardUpdate = {};
  (Object.keys(after) as (keyof CardLabels)[]).forEach((key) => {
    const next = after[key].trim();
    if (next !== before[key].trim()) changes[key] = next || null;
  });
  return changes;
}

/**
 * Name, set and number. Labels only -- nothing measured depends on them -- so
 * the check page offers them folded away and the header can edit them later.
 * Max lengths mirror backend models/card.py.
 */
export default function CardLabelFields({
  value,
  onChange,
  nameRequired = false,
}: {
  value: CardLabels;
  onChange: (next: CardLabels) => void;
  /** A mail-in needs a name: the operator matches the physical card by it. */
  nameRequired?: boolean;
}) {
  const t = useTranslations();
  return (
    <>
      <TextField
        value={value.card_name}
        onChange={(v) => onChange({ ...value, card_name: v })}
        isRequired={nameRequired}
        fullWidth
      >
        <Label>{t.checkFlow.cardName}</Label>
        <Input maxLength={200} />
      </TextField>
      <TextField value={value.set_name} onChange={(v) => onChange({ ...value, set_name: v })} fullWidth>
        <Label>{t.checkFlow.setName}</Label>
        <Input maxLength={200} />
      </TextField>
      <TextField
        value={value.card_number}
        onChange={(v) => onChange({ ...value, card_number: v })}
        fullWidth
      >
        <Label>{t.checkFlow.cardNumber}</Label>
        <Input maxLength={50} />
      </TextField>
    </>
  );
}
