"use client";

import { useState, type FormEvent } from "react";
import {
  Card,
  Description,
  Input,
  Label,
  ListBox,
  Select,
  TextArea,
  TextField,
} from "@heroui/react";
import Button from "@/components/Button";
import { ApiError, sendContactMessage, type ContactTopic } from "@/lib/api";
import { useBrand } from "@/lib/use-brand";
import { useBranding } from "@/lib/branding-context";
import { useLocale, useTranslations } from "@/lib/i18n/context";
import { withBusinessName } from "@/lib/use-business-name";

/** Shortest message the backend will accept -- mirrors _MESSAGE in
 *  backend/zgrader/schemas/contact.py. Checked here only so the reader gets a
 *  sentence instead of a 422. */
const MIN_MESSAGE_LENGTH = 10;

export default function ContactForm() {
  const t = useTranslations();
  const { locale } = useLocale();
  const { business_name, care_business_name } = useBranding();
  // Whichever side of the site they came from is the likelier subject, so it
  // is preselected. Still changeable -- this is a guess, not a routing rule.
  const brand = useBrand();

  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [topic, setTopic] = useState<ContactTopic>(brand === "care" ? "care" : "lab");
  const [subject, setSubject] = useState("");
  const [code, setCode] = useState("");
  const [message, setMessage] = useState("");
  // The honeypot's state. Never shown, never set by a person.
  const [website, setWebsite] = useState("");

  const [submitting, setSubmitting] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);

    // The backend enforces this too; checking here turns a 422 into a
    // sentence next to the field that caused it.
    if (message.trim().length < MIN_MESSAGE_LENGTH) {
      setError(t.contact.errorMessageShort);
      return;
    }

    setSubmitting(true);
    try {
      await sendContactMessage({
        name: name.trim(),
        email: email.trim(),
        topic,
        subject: subject.trim(),
        message: message.trim(),
        language: locale,
        submission_code: code.trim() || null,
        website,
      });
      setSent(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t.contact.errorGeneric);
    } finally {
      setSubmitting(false);
    }
  }

  function reset() {
    setSubject("");
    setCode("");
    setMessage("");
    setSent(false);
    setError(null);
  }

  if (sent) {
    return (
      <Card className="mt-6">
        <Card.Header>
          <Card.Title>{t.contact.successTitle}</Card.Title>
        </Card.Header>
        <Card.Content className="flex flex-col items-start gap-4">
          <p className="text-sm text-muted">{t.contact.successBody}</p>
          <Button variant="outline" onPress={reset}>
            {t.contact.successAgain}
          </Button>
        </Card.Content>
      </Card>
    );
  }

  return (
    <Card className="mt-6">
      <Card.Header>
        <Card.Title>{t.contact.formTitle}</Card.Title>
        <Card.Description>{t.contact.formLede}</Card.Description>
      </Card.Header>
      <Card.Content>
        <form className="flex flex-col gap-4" onSubmit={handleSubmit}>
          <div className="grid gap-4 sm:grid-cols-2">
            <TextField value={name} onChange={setName} isRequired fullWidth>
              <Label>{t.contact.nameLabel}</Label>
              <Input placeholder={t.contact.namePlaceholder} />
            </TextField>

            <TextField type="email" value={email} onChange={setEmail} isRequired fullWidth>
              <Label>{t.contact.emailLabel}</Label>
              <Input placeholder={t.contact.emailPlaceholder} />
              <Description>{t.contact.emailHelp}</Description>
            </TextField>
          </div>

          {/* Both option labels come from Settings, so renaming either brand
              in admin renames them here rather than leaving the form naming a
              business that no longer exists. */}
          <Select.Root
            selectedKey={topic}
            onSelectionChange={(key) => setTopic(String(key) as ContactTopic)}
            isRequired
            fullWidth
          >
            <Label>{t.contact.topicLabel}</Label>
            <Select.Trigger>
              <Select.Value />
              <Select.Indicator />
            </Select.Trigger>
            <Select.Popover>
              <ListBox>
                <ListBox.Item id="lab" textValue={withBusinessName(t.contact.topicLab, business_name)}>
                  {withBusinessName(t.contact.topicLab, business_name)}
                </ListBox.Item>
                <ListBox.Item
                  id="care"
                  textValue={withBusinessName(t.contact.topicCare, care_business_name)}
                >
                  {withBusinessName(t.contact.topicCare, care_business_name)}
                </ListBox.Item>
                <ListBox.Item id="other" textValue={t.contact.topicOther}>
                  {t.contact.topicOther}
                </ListBox.Item>
              </ListBox>
            </Select.Popover>
          </Select.Root>

          <TextField value={subject} onChange={setSubject} isRequired fullWidth>
            <Label>{t.contact.subjectLabel}</Label>
            <Input placeholder={t.contact.subjectPlaceholder} />
          </TextField>

          <TextField value={code} onChange={setCode} fullWidth>
            <Label>
              {t.contact.codeLabel}{" "}
              <span className="font-normal text-muted">({t.contact.codeOptional})</span>
            </Label>
            <Input placeholder={t.contact.codePlaceholder} />
            <Description>{t.contact.codeHelp}</Description>
          </TextField>

          <TextField value={message} onChange={setMessage} isRequired fullWidth>
            <Label>{t.contact.messageLabel}</Label>
            <TextArea rows={6} placeholder={t.contact.messagePlaceholder} />
          </TextField>

          {/*
            Honeypot. Positioned off-screen rather than `display: none`,
            because the simpler bots skip hidden fields but happily fill one
            that is merely out of view -- which is the whole point. aria-hidden
            and tabIndex={-1} keep it away from keyboard and screen-reader
            users, for whom it would otherwise be an unexplained required-
            looking field they cannot see.

            A filled value does not block submission here: the backend accepts
            it, discards it, and returns success, so nothing tells whoever
            wrote the bot which field gave them away.
          */}
          <div aria-hidden="true" className="pointer-events-none absolute left-[-9999px] h-px w-px overflow-hidden">
            <label htmlFor="contact-website">Website</label>
            <input
              id="contact-website"
              name="website"
              type="text"
              tabIndex={-1}
              autoComplete="off"
              value={website}
              onChange={(event) => setWebsite(event.target.value)}
            />
          </div>

          {error && (
            <p role="alert" className="text-sm text-accent">
              {error}
            </p>
          )}

          <div>
            <Button type="submit" variant="primary" isDisabled={submitting} className="btn-press">
              {submitting ? t.contact.sending : t.contact.submit}
            </Button>
          </div>
        </form>
      </Card.Content>
    </Card>
  );
}
