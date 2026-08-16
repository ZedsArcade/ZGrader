"use client";

import Link from "next/link";
import StartCheckLink from "@/components/StartCheckLink";
import { Card, buttonVariants, cn } from "@heroui/react";
import PageHeader from "@/components/PageHeader";
import { useTranslations } from "@/lib/i18n/context";
import { useFreeAllowanceSentence } from "@/lib/use-pricing";

export default function HowItWorksClient() {
  const t = useTranslations();
  // Null until /catalog/pricing answers, and the CTA reads properly without
  // it -- the figure is never written into the copy.
  const freeAllowance = useFreeAllowanceSentence();

  const steps = [
    { title: t.howItWorks.step1Title, body: t.howItWorks.step1Body },
    { title: t.howItWorks.step2Title, body: t.howItWorks.step2Body },
    { title: t.howItWorks.step3Title, body: t.howItWorks.step3Body },
    { title: t.howItWorks.step4Title, body: t.howItWorks.step4Body },
  ];

  const faqs = [
    { q: t.howItWorks.faq1Q, a: t.howItWorks.faq1A },
    { q: t.howItWorks.faq2Q, a: t.howItWorks.faq2A },
    { q: t.howItWorks.faq3Q, a: t.howItWorks.faq3A },
    { q: t.howItWorks.faq4Q, a: t.howItWorks.faq4A },
    { q: t.howItWorks.faq5Q, a: t.howItWorks.faq5A },
    { q: t.howItWorks.faq6Q, a: t.howItWorks.faq6A },
  ];

  return (
    <>
      <PageHeader title={t.howItWorks.title} lede={t.howItWorks.subtitle} />

      <ol className="verdict-reveal flex flex-col gap-4">
        {steps.map((step, i) => (
          <li key={step.title}>
            <Card className="interactive-card">
              <Card.Content>
                <div className="flex gap-4">
                  <span
                    aria-hidden="true"
                    className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-sm font-semibold"
                    style={{
                      backgroundColor: "var(--neon-pink)",
                      color: "var(--neon-foreground)",
                    }}
                  >
                    {i + 1}
                  </span>
                  <div className="flex flex-col gap-1">
                    <h2 className="text-base font-semibold text-foreground">{step.title}</h2>
                    <p className="text-sm leading-relaxed text-muted">{step.body}</p>
                  </div>
                </div>
              </Card.Content>
            </Card>
          </li>
        ))}
      </ol>

      <h2 className="mt-10 text-2xl font-bold tracking-tight text-foreground">
        {t.howItWorks.faqTitle}
      </h2>
      <div className="mt-4 flex flex-col gap-3">
        {faqs.map((faq) => (
          <details
            key={faq.q}
            className="group rounded-xl border border-border bg-surface-secondary p-4"
          >
            <summary className="cursor-pointer list-none text-sm font-semibold text-foreground marker:content-none">
              <span className="mr-2 text-accent" aria-hidden="true">
                {/* Rotates when the browser opens the <details>. */}
                <span className="inline-block transition-transform group-open:rotate-90">
                  &rsaquo;
                </span>
              </span>
              {faq.q}
            </summary>
            <p className="mt-2 pl-5 text-sm leading-relaxed text-muted">{faq.a}</p>
          </details>
        ))}
      </div>

      {/* The FAQ above admits surface analysis is the weakest category; this
          is where someone who wants to know why goes next. */}
      <div className="mt-4">
        <Link
          href="/methodology"
          className="text-sm font-semibold text-accent link-accent-hover hover:underline"
        >
          {t.howItWorks.methodologyLink} &rsaquo;
        </Link>
      </div>

      <Card className="interactive-card mt-8">
        <Card.Header>
          <Card.Title>{t.howItWorks.ctaTitle}</Card.Title>
        </Card.Header>
        <Card.Content>
          <p className="text-sm text-muted">
            {t.howItWorks.ctaBody}
            {freeAllowance ? ` ${freeAllowance}` : ""}
          </p>
          <div className="mt-4">
            <StartCheckLink
              className={cn(buttonVariants({ variant: "primary" }), "btn-press btn-neon-hover")}
            >
              {t.landing.getStarted}
            </StartCheckLink>
          </div>
        </Card.Content>
      </Card>
    </>
  );
}
