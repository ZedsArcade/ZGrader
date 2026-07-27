"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { Card, Input, Label, TextField } from "@heroui/react";
import Button from "@/components/Button";
import * as api from "@/lib/api";
import { useTranslations } from "@/lib/i18n/context";

export default function ForgotPasswordPage() {
  const t = useTranslations();
  const [email, setEmail] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [sent, setSent] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    try {
      await api.requestPasswordReset(email);
    } catch {
      // Swallowed on purpose. The endpoint answers 204 whether or not the
      // address exists; surfacing a network hiccup differently from a
      // success would start leaking the same information the endpoint is
      // careful not to.
    } finally {
      setSubmitting(false);
      setSent(true);
    }
  }

  return (
    <Card className="mx-auto max-w-md">
      <Card.Header>
        <Card.Title>{t.forgotPassword.title}</Card.Title>
        <Card.Description>{t.forgotPassword.subtitle}</Card.Description>
      </Card.Header>
      <Card.Content>
        {sent ? (
          <div className="flex flex-col gap-4">
            <p className="text-sm text-muted">{t.forgotPassword.sent}</p>
            <Link href="/login" className="text-sm font-semibold text-accent link-accent-hover">
              {t.forgotPassword.backToLogin}
            </Link>
          </div>
        ) : (
          <form className="flex flex-col gap-4" onSubmit={handleSubmit}>
            <TextField type="email" value={email} onChange={setEmail} isRequired fullWidth>
              <Label>{t.forgotPassword.email}</Label>
              <Input />
            </TextField>
            <Button type="submit" variant="primary" isDisabled={submitting} fullWidth>
              {submitting ? t.forgotPassword.submitting : t.forgotPassword.submit}
            </Button>
            <Link href="/login" className="text-sm text-muted link-accent-hover hover:text-accent">
              {t.forgotPassword.backToLogin}
            </Link>
          </form>
        )}
      </Card.Content>
    </Card>
  );
}
