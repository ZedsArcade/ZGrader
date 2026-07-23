"use client";

import Link from "next/link";
import { Card, buttonVariants, cn } from "@heroui/react";
import { useTranslations } from "@/lib/i18n/context";

export default function HomePage() {
  const t = useTranslations();
  return (
    <>
      <section
        className="flex flex-col items-start gap-5 rounded-2xl px-6 py-14"
        style={{
          background: "radial-gradient(ellipse at top left, var(--neon-glow), transparent 60%), var(--bg)",
        }}
      >
        <svg width="40" height="40" viewBox="0 0 40 40" fill="none" aria-hidden="true" className="text-accent">
          <path
            d="M20 3 L34 14 L28 36 L12 36 L6 14 Z"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinejoin="round"
          />
          <path d="M20 3 L20 36 M6 14 L34 14 M12 36 L20 14 L28 36" stroke="currentColor" strokeWidth="1" opacity="0.6" />
        </svg>
        <h1 className="text-4xl font-bold tracking-tight text-foreground sm:text-5xl">
          {t.landing.title}
        </h1>
        <p className="max-w-2xl text-lg text-muted">{t.landing.subtitle}</p>
        <div className="flex flex-wrap gap-3">
          <Link href="/register" className={cn(buttonVariants({ variant: "primary" }), "btn-press btn-neon-hover")}>
            {t.landing.getStarted}
          </Link>
          <Link href="/login" className={cn(buttonVariants({ variant: "outline" }), "btn-press btn-neon-hover")}>
            {t.landing.login}
          </Link>
        </div>
      </section>

      <div className="grid gap-5 py-6 sm:grid-cols-2 lg:grid-cols-3">
        <Card className="interactive-card">
          <Card.Header>
            <Card.Title>{t.landing.feature1Title}</Card.Title>
          </Card.Header>
          <Card.Content>
            <p className="text-sm text-muted">{t.landing.feature1Body}</p>
          </Card.Content>
        </Card>
        <Card className="interactive-card">
          <Card.Header>
            <Card.Title>{t.landing.feature2Title}</Card.Title>
          </Card.Header>
          <Card.Content>
            <p className="text-sm text-muted">{t.landing.feature2Body}</p>
          </Card.Content>
        </Card>
        <Card className="interactive-card">
          <Card.Header>
            <Card.Title>{t.landing.feature3Title}</Card.Title>
          </Card.Header>
          <Card.Content>
            <p className="text-sm text-muted">{t.landing.feature3Body}</p>
          </Card.Content>
        </Card>
      </div>

      <Card className="mt-4">
        <Card.Header>
          <Card.Title>{t.landing.noteTitle}</Card.Title>
        </Card.Header>
        <Card.Content>
          <p className="text-sm text-muted">{t.landing.noteBody}</p>
        </Card.Content>
      </Card>
    </>
  );
}
