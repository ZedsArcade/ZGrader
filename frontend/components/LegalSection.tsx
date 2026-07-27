"use client";

/** One numbered clause of a legal page. Kept as a component so Terms and
 *  Privacy read identically and a change lands in both. */
export default function LegalSection({ title, body }: { title: string; body: string }) {
  return (
    <section className="flex flex-col gap-2">
      <h2 className="text-base font-semibold text-foreground">{title}</h2>
      <p className="text-sm leading-relaxed text-muted">{body}</p>
    </section>
  );
}
