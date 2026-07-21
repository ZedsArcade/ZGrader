"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Card, Spinner } from "@heroui/react";
import { verifyEmail, ApiError } from "@/lib/api";
import { useTranslations } from "@/lib/i18n/context";

export default function VerifyClient({ token }: { token: string }) {
  const [status, setStatus] = useState<"pending" | "success" | "error">("pending");
  const [message, setMessage] = useState<string | null>(null);
  const t = useTranslations();

  useEffect(() => {
    verifyEmail(token)
      .then(() => setStatus("success"))
      .catch((err) => {
        setStatus("error");
        setMessage(err instanceof ApiError ? err.message : t.verify.failed);
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  return (
    <Card className="mx-auto max-w-md">
      <Card.Header>
        <Card.Title>{t.verify.title}</Card.Title>
      </Card.Header>
      <Card.Content>
        {status === "pending" && (
          <div className="flex items-center gap-3 text-sm text-muted">
            <Spinner size="sm" />
            {t.verify.verifying}
          </div>
        )}
        {status === "success" && (
          <p className="text-sm text-success">
            {t.verify.success}{" "}
            <Link href="/login" className="text-accent hover:underline link-accent-hover">
              {t.verify.loginLink}
            </Link>
            .
          </p>
        )}
        {status === "error" && <p className="text-sm text-danger">{message}</p>}
      </Card.Content>
    </Card>
  );
}
