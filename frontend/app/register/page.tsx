"use client";

import { useEffect, useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Card, Checkbox, Description, FieldError, Input, Label, TextField } from "@heroui/react";
import Button from "@/components/Button";
import { useAuth } from "@/lib/auth-context";
import { ApiError } from "@/lib/api";
import { toastError, toastSuccess } from "@/lib/toast";
import { useTranslations } from "@/lib/i18n/context";

export default function RegisterPage() {
  const { register, user, loading } = useAuth();
  const router = useRouter();
  const t = useTranslations();

  // Someone who already has an account has no business on this form. This
  // covers typing /register directly, a stale bookmark, and the brief window
  // on first paint where StartCheckLink has not yet seen the restored session
  // and still points here. `replace` rather than `push` so Back does not
  // bounce them straight back to a page they cannot use.
  useEffect(() => {
    if (!loading && user) router.replace("/dashboard");
  }, [loading, user, router]);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [acceptTerms, setAcceptTerms] = useState(false);
  const [marketing, setMarketing] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [attempted, setAttempted] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setAttempted(true);
    // The backend rejects this too; checking here just gives a clearer
    // message than a 422 would.
    if (!acceptTerms) {
      toastError(t.register.acceptTermsRequired);
      return;
    }
    setSubmitting(true);
    try {
      await register(email, password, acceptTerms, marketing);
      // Signed in, but not yet verified -- say so, because submitting a card
      // will be refused until they click the link.
      toastSuccess(t.register.checkInbox);
      router.push("/dashboard");
    } catch (err) {
      toastError(err instanceof ApiError ? err.message : t.register.failed);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Card className="mx-auto max-w-md">
      <Card.Header>
        <Card.Title>{t.register.title}</Card.Title>
        <Card.Description>{t.register.subtitle}</Card.Description>
      </Card.Header>
      <Card.Content>
        <form className="flex flex-col gap-4" onSubmit={handleSubmit}>
          <TextField type="email" value={email} onChange={setEmail} isRequired fullWidth>
            <Label>{t.register.email}</Label>
            <Input />
          </TextField>
          <TextField
            type="password"
            value={password}
            onChange={setPassword}
            isRequired
            minLength={8}
            fullWidth
          >
            <Label>{t.register.password}</Label>
            <Input />
            <Description>{t.register.passwordHint}</Description>
            <FieldError />
          </TextField>

          {/* Recorded server-side with a timestamp and the terms version --
              without that there's no evidence of what anyone agreed to. */}
          {/* Not `isRequired`: that blocks submission with only a red ring
              and no explanation of what's wrong. handleSubmit refuses instead,
              and the message below says why. */}
          <Checkbox.Root isSelected={acceptTerms} onChange={setAcceptTerms}>
            <Checkbox.Content>
              <Checkbox.Control>
                <Checkbox.Indicator />
              </Checkbox.Control>
              <span className="text-sm">
                {t.register.acceptTerms}{" "}
                <Link href="/terms" target="_blank" className="underline text-accent">
                  {t.register.termsLink}
                </Link>
                {" / "}
                <Link href="/privacy" target="_blank" className="underline text-accent">
                  {t.register.privacyLink}
                </Link>
              </span>
            </Checkbox.Content>
          </Checkbox.Root>
          {attempted && !acceptTerms && (
            <p className="text-sm text-danger">{t.register.acceptTermsRequired}</p>
          )}

          <Checkbox.Root isSelected={marketing} onChange={setMarketing}>
            <Checkbox.Content>
              <Checkbox.Control>
                <Checkbox.Indicator />
              </Checkbox.Control>
              <span className="text-sm">{t.register.marketingOptIn}</span>
            </Checkbox.Content>
          </Checkbox.Root>

          <Button type="submit" variant="primary" isDisabled={submitting} fullWidth>
            {submitting ? t.register.submitting : t.register.submit}
          </Button>
        </form>
      </Card.Content>
    </Card>
  );
}
