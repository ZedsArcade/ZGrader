"use client";

import { Suspense, useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Card, Input, Label, TextField } from "@heroui/react";
import Button from "@/components/Button";
import GoogleSignInButton from "@/components/GoogleSignInButton";
import OAuthErrorToast from "@/components/OAuthErrorToast";
import { useAuth } from "@/lib/auth-context";
import { ApiError } from "@/lib/api";
import { toastError } from "@/lib/toast";
import { useTranslations } from "@/lib/i18n/context";

export default function LoginPage() {
  const { login } = useAuth();
  const router = useRouter();
  const t = useTranslations();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    try {
      const user = await login(email, password);
      router.push(user.role === "operator" ? "/admin" : "/dashboard");
    } catch (err) {
      toastError(err instanceof ApiError ? err.message : t.login.failed);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Card className="mx-auto max-w-md">
      {/* Suspended so reading search params doesn't opt this prerendered
          page out of static generation. */}
      <Suspense fallback={null}>
        <OAuthErrorToast />
      </Suspense>
      <Card.Header>
        <Card.Title>{t.login.title}</Card.Title>
      </Card.Header>
      <Card.Content>
        <form className="flex flex-col gap-4" onSubmit={handleSubmit}>
          <TextField type="email" value={email} onChange={setEmail} isRequired fullWidth>
            <Label>{t.login.email}</Label>
            <Input />
          </TextField>
          <TextField type="password" value={password} onChange={setPassword} isRequired fullWidth>
            <Label>{t.login.password}</Label>
            <Input />
          </TextField>
          <Button type="submit" variant="primary" isDisabled={submitting} fullWidth>
            {submitting ? t.login.submitting : t.login.submit}
          </Button>
          <Link
            href="/forgot-password"
            className="text-center text-sm text-muted link-accent-hover hover:text-accent"
          >
            {t.login.forgotPassword}
          </Link>
        </form>

        <div className="mt-4">
          <GoogleSignInButton />
        </div>
      </Card.Content>
    </Card>
  );
}
