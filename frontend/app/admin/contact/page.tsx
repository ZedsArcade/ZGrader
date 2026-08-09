"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Card, Checkbox, buttonVariants, cn } from "@heroui/react";
import Button from "@/components/Button";
import RequireAuth from "@/components/RequireAuth";
import Skeleton from "@/components/Skeleton";
import EmptyState from "@/components/EmptyState";
import ErrorState from "@/components/ErrorState";
import { useAuth } from "@/lib/auth-context";
import * as api from "@/lib/api";

/**
 * The operator's contact-form inbox.
 *
 * Exists because the enquiry is stored before it is emailed, and the email
 * currently does not go anywhere (SMTP is unconfigured). Until it does, this
 * page is the only way to read what anyone has sent -- which is why the
 * "not emailed" marker below is prominent rather than a footnote.
 */
function ContactInbox() {
  const { token } = useAuth();
  const [messages, setMessages] = useState<api.ContactMessage[] | null>(null);
  const [unhandledOnly, setUnhandledOnly] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    if (!token) return;
    setError(null);
    api
      .getContactMessages(token, { unhandledOnly })
      .then(setMessages)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load messages"));
  }, [token, unhandledOnly]);

  useEffect(load, [load]);

  async function toggleHandled(message: api.ContactMessage) {
    if (!token) return;
    try {
      const updated = await api.setContactMessageHandled(token, message.id, !message.handled);
      // Patch in place rather than reloading: with the "unhandled only" filter
      // on, a reload would make the row vanish the instant it is ticked, which
      // reads as the message being deleted.
      setMessages((current) =>
        current ? current.map((m) => (m.id === updated.id ? updated : m)) : current
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update message");
    }
  }

  return (
    <>
      <div className="mb-5 flex items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Contact messages</h1>
          <p className="text-sm text-muted">Enquiries sent through the public contact form.</p>
        </div>
        <Link
          href="/admin"
          className={cn(buttonVariants({ variant: "outline" }), "btn-press btn-neon-hover")}
        >
          Back to admin
        </Link>
      </div>

      <div className="mb-4">
        <Checkbox.Root isSelected={unhandledOnly} onChange={setUnhandledOnly}>
          <Checkbox.Content>
            <Checkbox.Control>
              <Checkbox.Indicator />
            </Checkbox.Control>
            <span className="text-sm">Unhandled only</span>
          </Checkbox.Content>
        </Checkbox.Root>
      </div>

      {error && <ErrorState message={error} onRetry={load} />}

      {!error && messages === null && (
        <div className="flex flex-col gap-3">
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-24 w-full" />
        </div>
      )}

      {!error && messages !== null && messages.length === 0 && (
        <EmptyState
          title="Nothing here"
          description={
            unhandledOnly
              ? "No unhandled messages. Untick the filter to see the rest."
              : "No one has used the contact form yet."
          }
        />
      )}

      {!error && messages !== null && messages.length > 0 && (
        <div className="flex flex-col gap-4">
          {messages.map((message) => (
            <Card key={message.id} className={message.handled ? "opacity-60" : undefined}>
              <Card.Header>
                <Card.Title>{message.subject}</Card.Title>
                <Card.Description>
                  {message.name} &lt;{message.email}&gt; &middot;{" "}
                  {new Date(message.created_at).toLocaleString()}
                </Card.Description>
              </Card.Header>
              <Card.Content className="flex flex-col gap-3">
                <div className="flex flex-wrap items-center gap-2 text-xs">
                  <span className="rounded bg-surface-secondary px-2 py-1 uppercase tracking-wide text-muted">
                    {message.topic}
                  </span>
                  <span className="rounded bg-surface-secondary px-2 py-1 uppercase tracking-wide text-muted">
                    {message.language}
                  </span>
                  {message.submission_code && (
                    <Link
                      href={`/admin/${message.submission_code}`}
                      className="rounded px-2 py-1 text-accent underline link-accent-hover"
                    >
                      {message.submission_code}
                    </Link>
                  )}
                  {!message.notified && (
                    // The operator was never emailed about this one, so the
                    // row on screen is the only copy. Worth saying loudly.
                    // `grade-warn` is the shared amber chip utility from
                    // motion.css -- it sets both the tint and the text colour,
                    // so it is used bare rather than as a text-* class.
                    <span className="grade-warn rounded px-2 py-1 uppercase tracking-wide">
                      not emailed
                    </span>
                  )}
                </div>

                {/* pre-wrap so the sender's own paragraphing survives. */}
                <p className="whitespace-pre-wrap text-sm leading-relaxed text-foreground">
                  {message.message}
                </p>

                <div className="flex flex-wrap gap-2">
                  <a
                    href={`mailto:${message.email}?subject=${encodeURIComponent(`Re: ${message.subject}`)}`}
                    className={cn(buttonVariants({ variant: "primary", size: "sm" }), "btn-press")}
                  >
                    Reply
                  </a>
                  <Button variant="outline" size="sm" onPress={() => toggleHandled(message)}>
                    {message.handled ? "Mark unhandled" : "Mark handled"}
                  </Button>
                </div>
              </Card.Content>
            </Card>
          ))}
        </div>
      )}
    </>
  );
}

export default function AdminContactPage() {
  return (
    <RequireAuth role="operator">
      <ContactInbox />
    </RequireAuth>
  );
}
