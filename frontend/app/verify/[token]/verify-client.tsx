"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
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
    <div className="card" style={{ maxWidth: 460, margin: "0 auto" }}>
      <h1>Email verification</h1>
      {status === "pending" && <p className="spinner-text">Verifying…</p>}
      {status === "success" && (
        <div className="alert alert-success" style={{ marginTop: 16 }}>
          Your email is verified. You can now <Link href="/login">log in</Link>.
        </div>
      )}
      {status === "error" && (
        <div className="alert alert-error" style={{ marginTop: 16 }}>
          {message}
        </div>
      )}
    </div>
  );
}
