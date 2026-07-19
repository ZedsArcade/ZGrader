"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { Button, Card, Input, Label, TextField } from "@heroui/react";
import { useAuth } from "@/lib/auth-context";
import { ApiError } from "@/lib/api";
import { toastError } from "@/lib/toast";

export default function RegisterPage() {
  const { register } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    try {
      await register(email, password);
      router.push("/dashboard");
    } catch (err) {
      toastError(err instanceof ApiError ? err.message : "Registration failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Card className="mx-auto max-w-md">
      <Card.Header>
        <Card.Title>Create an account</Card.Title>
        <Card.Description>Register to submit cards and track your reports.</Card.Description>
      </Card.Header>
      <Card.Content>
        <form className="flex flex-col gap-4" onSubmit={handleSubmit}>
          <TextField type="email" value={email} onChange={setEmail} isRequired fullWidth>
            <Label>Email</Label>
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
            <Label>Password</Label>
            <Input />
          </TextField>
          <Button type="submit" variant="primary" isDisabled={submitting} fullWidth>
            {submitting ? "Creating account…" : "Register"}
          </Button>
        </form>
      </Card.Content>
    </Card>
  );
}
