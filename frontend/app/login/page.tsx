"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { Button, Card, Input, Label, TextField } from "@heroui/react";
import { useAuth } from "@/lib/auth-context";
import { ApiError } from "@/lib/api";
import { toastError } from "@/lib/toast";

export default function LoginPage() {
  const { login } = useAuth();
  const router = useRouter();
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
      toastError(err instanceof ApiError ? err.message : "Login failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Card className="mx-auto max-w-md">
      <Card.Header>
        <Card.Title>Log in</Card.Title>
      </Card.Header>
      <Card.Content>
        <form className="flex flex-col gap-4" onSubmit={handleSubmit}>
          <TextField type="email" value={email} onChange={setEmail} isRequired fullWidth>
            <Label>Email</Label>
            <Input />
          </TextField>
          <TextField type="password" value={password} onChange={setPassword} isRequired fullWidth>
            <Label>Password</Label>
            <Input />
          </TextField>
          <Button type="submit" variant="primary" isDisabled={submitting} fullWidth>
            {submitting ? "Logging in…" : "Log in"}
          </Button>
        </form>
      </Card.Content>
    </Card>
  );
}
