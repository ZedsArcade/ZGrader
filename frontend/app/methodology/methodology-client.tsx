"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { Card, buttonVariants, cn } from "@heroui/react";
import PageHeader from "@/components/PageHeader";
import { useTranslations } from "@/lib/i18n/context";
import { useGradingCompanies, withCompanies } from "@/lib/use-grading-companies";

/** One figure: the picture, then what it shows. Plain <img> with an explicit
 *  aspect-preserving width -- these are static files in /public, so there's
 *  no token to attach and none of the fetch-to-blob handling the
 *  authenticated report images need. */
function Figure({ src, alt, caption }: { src: string; alt: string; caption: string }) {
  return (
    <figure className="flex flex-col gap-2">
      <img
        src={src}
        alt={alt}
        className="w-full max-w-sm self-center rounded-lg border border-border"
      />
      <figcaption className="text-xs leading-relaxed text-muted">{caption}</figcaption>
    </figure>
  );
}

/** A category section: what it measures, how, the figure, and -- given the
 *  point of this page -- where it fails, which is never omitted. */
function Category({
  title,
  measuresLabel,
  measuresBody,
  howLabel,
  howBody,
  wrongLabel,
  wrongBody,
  children,
}: {
  title: string;
  measuresLabel: string;
  measuresBody: string;
  howLabel: string;
  howBody: string;
  wrongLabel: string;
  wrongBody: string;
  children?: ReactNode;
}) {
  return (
    <Card className="interactive-card">
      <Card.Header>
        <Card.Title>{title}</Card.Title>
      </Card.Header>
      <Card.Content className="flex flex-col gap-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="flex flex-col gap-4">
            <Detail label={measuresLabel} body={measuresBody} />
            <Detail label={howLabel} body={howBody} />
          </div>
          {children}
        </div>
        <div className="rounded-lg border border-dashed border-border bg-surface-secondary p-3">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted">{wrongLabel}</p>
          <p className="mt-1 text-sm leading-relaxed text-muted">{wrongBody}</p>
        </div>
      </Card.Content>
    </Card>
  );
}

function Detail({ label, body }: { label: string; body: string }) {
  return (
    <div>
      <p className="text-xs font-semibold uppercase tracking-wide text-muted">{label}</p>
      <p className="mt-1 text-sm leading-relaxed text-muted">{body}</p>
    </div>
  );
}

export default function MethodologyClient() {
  const t = useTranslations();
  const companies = useGradingCompanies();

  return (
    <>
      <PageHeader title={t.methodology.title} lede={t.methodology.subtitle} />

      <div className="verdict-reveal flex flex-col gap-5">
        {/* Said up front, not buried: the reader is about to look at six
            pictures of a card that doesn't exist, and finding that out later
            would undo exactly the trust this page is here to build. */}
        <Card>
          <Card.Header>
            <Card.Title>{t.methodology.demoTitle}</Card.Title>
          </Card.Header>
          <Card.Content>
            <p className="text-sm leading-relaxed text-muted">{t.methodology.demoBody}</p>
          </Card.Content>
        </Card>

        <Card>
          <Card.Header>
            <Card.Title>{t.methodology.prepTitle}</Card.Title>
          </Card.Header>
          <Card.Content>
            <p className="text-sm leading-relaxed text-muted">{t.methodology.prepBody}</p>
          </Card.Content>
        </Card>

        <Category
          title={t.methodology.centeringTitle}
          measuresLabel={t.methodology.centeringMeasures}
          measuresBody={t.methodology.centeringMeasuresBody}
          howLabel={t.methodology.centeringHow}
          howBody={t.methodology.centeringHowBody}
          wrongLabel={t.methodology.centeringWrong}
          wrongBody={t.methodology.centeringWrongBody}
        >
          <Figure
            src="/methodology/centering.jpg"
            alt={t.methodology.centeringAlt}
            caption={t.methodology.centeringCaption}
          />
        </Category>

        <Category
          title={t.methodology.cornersTitle}
          measuresLabel={t.methodology.cornersMeasures}
          measuresBody={t.methodology.cornersMeasuresBody}
          howLabel={t.methodology.cornersHow}
          howBody={t.methodology.cornersHowBody}
          wrongLabel={t.methodology.cornersWrong}
          wrongBody={t.methodology.cornersWrongBody}
        >
          <Figure
            src="/methodology/corner.jpg"
            alt={t.methodology.cornersAlt}
            caption={t.methodology.cornersCaption}
          />
        </Category>

        <Category
          title={t.methodology.edgesTitle}
          measuresLabel={t.methodology.edgesMeasures}
          measuresBody={t.methodology.edgesMeasuresBody}
          howLabel={t.methodology.edgesHow}
          howBody={t.methodology.edgesHowBody}
          wrongLabel={t.methodology.edgesWrong}
          wrongBody={t.methodology.edgesWrongBody}
        >
          <Figure
            src="/methodology/edges.jpg"
            alt={t.methodology.edgesAlt}
            caption={t.methodology.edgesCaption}
          />
        </Category>

        {/* The surface section carries two figures rather than one: the pair
            is the argument. One picture of a clean result would prove
            nothing -- the before/after is what shows the false positives
            being caught, and the ones that aren't. */}
        <Category
          title={t.methodology.surfaceTitle}
          measuresLabel={t.methodology.surfaceMeasures}
          measuresBody={t.methodology.surfaceMeasuresBody}
          howLabel={t.methodology.surfaceHow}
          howBody={t.methodology.surfaceHowBody}
          wrongLabel={t.methodology.surfaceWrong}
          wrongBody={t.methodology.surfaceWrongBody}
        >
          <div className="flex flex-col gap-4">
            <Figure
              src="/methodology/surface-raw.jpg"
              alt={t.methodology.surfaceRawAlt}
              caption={t.methodology.surfaceRawCaption}
            />
            <Figure
              src="/methodology/surface-filtered.jpg"
              alt={t.methodology.surfaceFilteredAlt}
              caption={t.methodology.surfaceFilteredCaption}
            />
          </div>
        </Category>

        <Category
          title={t.methodology.creasesTitle}
          measuresLabel={t.methodology.creasesMeasures}
          measuresBody={t.methodology.creasesMeasuresBody}
          howLabel={t.methodology.creasesHow}
          howBody={t.methodology.creasesHowBody}
          wrongLabel={t.methodology.creasesWrong}
          wrongBody={t.methodology.creasesWrongBody}
        >
          <Figure
            src="/methodology/crease.jpg"
            alt={t.methodology.creasesAlt}
            caption={t.methodology.creasesCaption}
          />
        </Category>

        <Card>
          <Card.Header>
            <Card.Title>{t.methodology.confidenceTitle}</Card.Title>
          </Card.Header>
          <Card.Content>
            <p className="text-sm text-muted">{t.methodology.confidenceBody}</p>
            <ul className="mt-3 flex flex-col gap-2">
              {[
                t.methodology.confidence1,
                t.methodology.confidence2,
                t.methodology.confidence3,
                t.methodology.confidence4,
              ].map((line) => (
                <li key={line} className="flex gap-2 text-sm leading-relaxed text-muted">
                  <span aria-hidden="true" className="text-accent">
                    &bull;
                  </span>
                  <span>{line}</span>
                </li>
              ))}
            </ul>
          </Card.Content>
        </Card>

        <Card>
          <Card.Header>
            <Card.Title>{t.methodology.adjustTitle}</Card.Title>
          </Card.Header>
          <Card.Content>
            <p className="text-sm leading-relaxed text-muted">{t.methodology.adjustBody}</p>
          </Card.Content>
        </Card>

        <Card>
          <Card.Header>
            <Card.Title>{t.methodology.notTitle}</Card.Title>
          </Card.Header>
          <Card.Content>
            {/* Company names come from the enabled list, never hardcoded, so
                this page can't name a company the operator has switched off. */}
            <p className="text-sm leading-relaxed text-muted">
              {withCompanies(t.methodology.notBody, companies)}
            </p>
          </Card.Content>
        </Card>

        <Card className="interactive-card">
          <Card.Header>
            <Card.Title>{t.methodology.ctaTitle}</Card.Title>
          </Card.Header>
          <Card.Content>
            <p className="text-sm text-muted">{t.methodology.ctaBody}</p>
            <div className="mt-4">
              <Link
                href="/register"
                className={cn(buttonVariants({ variant: "primary" }), "btn-press btn-neon-hover")}
              >
                {t.landing.getStarted}
              </Link>
            </div>
          </Card.Content>
        </Card>
      </div>
    </>
  );
}
