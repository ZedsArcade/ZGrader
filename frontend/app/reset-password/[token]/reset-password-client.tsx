"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { Card, Description, FieldError, Input, Label, TextField } from "@heroui/react";
import Button from "@/components/Button";
import * as api from "@/lib/api";
import { useTranslations } from "@/lib/i18n/context";

export default function ResetPasswordClient({ token }: { token: string }) {
  const t = useTranslations();
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await api.resetPassword(token, password);
      setDone(true);
    } catch (err) {
      // The endpoint gives the same answer for an unknown, used and expired
      // token, so this message covers all three without guessing.
      setError(err instanceof api.ApiError ? err.message : t.resetPassword.failed);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Card className="mx-auto max-w-md">
      <Card.Header>
        <Card.Title>{t.resetPassword.title}</Card.Title>
      </Card.Header>
      <Card.Content>
        {done ? (
          <div className="flex flex-col gap-4">
            <p className="text-sm text-muted">{t.resetPassword.success}</p>
            <Link href="/login" className="text-sm font-semibold text-accent link-accent-hover">
              {t.resetPassword.loginLink}
            </Link>
          </div>
        ) : (
          <form className="flex flex-col gap-4" onSubmit={handleSubmit}>
            <TextField
              type="password"
              value={password}
              onChange={setPassword}
              isRequired
              minLength={8}
              fullWidth
            >
              <Label>{t.resetPassword.password}</Label>
              <Input />
              <Description>{t.resetPassword.passwordHint}</Description>
              <FieldError />
            </TextField>
            {error && (
              <div className="flex flex-col gap-2">
                <p className="text-sm text-danger">{error}</p>
                <Link
                  href="/forgot-password"
                  className="text-sm font-semibold text-accent link-accent-hover"
                >
                  {t.resetPassword.requestNew}
                </Link>
              </div>
            )}
            <Button type="submit" variant="primary" isDisabled={submitting} fullWidth>
              {submitting ? t.resetPassword.submitting : t.resetPassword.submit}
            </Button>
          </form>
        )}
      </Card.Content>
    </Card>
  );
}
