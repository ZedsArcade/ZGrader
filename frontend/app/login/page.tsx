"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { Button, Card, Input, Label, TextField } from "@heroui/react";
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
        </form>
      </Card.Content>
    </Card>
  );
}
