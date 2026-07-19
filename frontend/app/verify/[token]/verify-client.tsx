"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Card, Spinner } from "@heroui/react";
import { verifyEmail, ApiError } from "@/lib/api";

export default function VerifyClient({ token }: { token: string }) {
  const [status, setStatus] = useState<"pending" | "success" | "error">("pending");
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    verifyEmail(token)
      .then(() => setStatus("success"))
      .catch((err) => {
        setStatus("error");
        setMessage(err instanceof ApiError ? err.message : "Verification failed");
      });
  }, [token]);

  return (
    <Card className="mx-auto max-w-md">
      <Card.Header>
        <Card.Title>Email verification</Card.Title>
      </Card.Header>
      <Card.Content>
        {status === "pending" && (
          <div className="flex items-center gap-3 text-sm text-muted">
            <Spinner size="sm" />
            Verifying…
          </div>
        )}
        {status === "success" && (
          <p className="text-sm text-success">
            Your email is verified. You can now{" "}
            <Link href="/login" className="text-accent hover:underline">
              log in
            </Link>
            .
          </p>
        )}
        {status === "error" && <p className="text-sm text-danger">{message}</p>}
      </Card.Content>
    </Card>
  );
}
