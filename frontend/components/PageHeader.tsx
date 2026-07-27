"use client";

import type { ReactNode } from "react";

/** Shared title block for the public marketing and legal pages, so they all
 *  open the same way instead of each inventing its own heading sizes. */
export default function PageHeader({
  title,
  lede,
  meta,
}: {
  title: string;
  lede?: string;
  meta?: ReactNode;
}) {
  return (
    <header className="verdict-reveal flex flex-col gap-3 pb-8">
      <h1 className="text-3xl font-bold tracking-tight text-foreground sm:text-4xl">{title}</h1>
      {lede && <p className="max-w-2xl text-lg text-muted">{lede}</p>}
      {meta && <p className="text-xs text-muted">{meta}</p>}
    </header>
  );
}
