"use client";

import Link from "next/link";
import { Card, buttonVariants } from "@heroui/react";
import { useTranslations } from "@/lib/i18n/context";

export default function HomePage() {
  const t = useTranslations();
  return (
    <>
      <section className="flex flex-col items-start gap-5 py-10">
        <h1 className="text-4xl font-bold tracking-tight text-foreground sm:text-5xl">
          {t.landing.title}
        </h1>
        <p className="max-w-2xl text-lg text-muted">{t.landing.subtitle}</p>
        <div className="flex flex-wrap gap-3">
          <Link href="/register" className={buttonVariants({ variant: "primary" })}>
            {t.landing.getStarted}
          </Link>
          <Link href="/login" className={buttonVariants({ variant: "outline" })}>
            {t.landing.login}
          </Link>
        </div>
      </section>

      <div className="grid gap-5 py-6 sm:grid-cols-2 lg:grid-cols-3">
        <Card>
          <Card.Header>
            <Card.Title>{t.landing.feature1Title}</Card.Title>
          </Card.Header>
          <Card.Content>
            <p className="text-sm text-muted">{t.landing.feature1Body}</p>
          </Card.Content>
        </Card>
        <Card>
          <Card.Header>
            <Card.Title>{t.landing.feature2Title}</Card.Title>
          </Card.Header>
          <Card.Content>
            <p className="text-sm text-muted">{t.landing.feature2Body}</p>
          </Card.Content>
        </Card>
        <Card>
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
