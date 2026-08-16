import type { Metadata } from "next";
import { notFound } from "next/navigation";
import PublicReport from "@/components/PublicReport";
import { cardTitle, fetchPublicReport } from "@/lib/public-report-server";
import { getServerBusinessName } from "@/lib/branding-server";
import { en } from "@/lib/i18n/en";
import { es } from "@/lib/i18n/es";

/**
 * A shared report, readable by anyone holding the link and nobody else.
 *
 * `/r/{token}` rather than anything containing `submission_code`: codes come
 * from a sequence, so a public route keyed on one would let anybody walk it and
 * read every customer's report.
 *
 * A **server** component, for two reasons that both matter here. `generateMetadata`
 * is server-only, and the link preview is the entire point of the feature -- a
 * client-rendered page unfurls in Discord as a blank card. And an ISR page gets
 * `s-maxage`/`stale-while-revalidate` from Next automatically, where a dynamic
 * one is served `private, no-cache, no-store`; the origin here is a home server
 * running OpenCV, so being cacheable at the edge is not a nicety.
 */

/** 60 seconds, chosen against revocation rather than load. Rotating a token is
 *  how a customer un-shares something, so an edge cache is the window in which
 *  a revoked link still opens -- a minute of that is acceptable, an hour is not.
 *  A minute still absorbs the burst that follows a link being posted, which is
 *  the load actually worth caching for. */
export const revalidate = 60;

/**
 * Empty, and required to be here.
 *
 * A dynamic segment with no `generateStaticParams` is rendered on demand and
 * served `private, no-cache, no-store, max-age=0, must-revalidate` -- which
 * would make `revalidate` above decorative and leave every view of a shared
 * link hitting the origin. Returning an empty array is what opts the route into
 * ISR for paths generated at runtime; see
 * next/dist/docs/01-app/03-api-reference/04-functions/generate-static-params.md,
 * "You must return an empty array from generateStaticParams ... in order to
 * revalidate (ISR) paths at runtime."
 *
 * Empty rather than a list of live tokens: enumerating them at build time would
 * put every share token into the build output, and the build runs in a Docker
 * stage where the backend is not reachable anyway.
 */
export async function generateStaticParams(): Promise<{ token: string }[]> {
  return [];
}

type Props = { params: Promise<{ token: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  // `params` is a Promise in this version of Next.
  const { token } = await params;
  const report = await fetchPublicReport(token);
  if (!report) {
    // Nothing describing the card, and still noindex -- a preview for a dead
    // link should say nothing at all rather than confirm a token existed.
    return { title: "Not found", robots: { index: false, follow: false } };
  }

  const siteName = await getServerBusinessName();
  // `?v=` carries the fingerprint of everything the image is drawn from, the
  // same idiom `serviceImageUrl` uses for an operator-replaced banner. The
  // server ignores the value and always renders current state; the parameter
  // exists so an adjusted report is a *different URL*, which is the only lever
  // that makes a crawler re-fetch rather than reuse what it cached.
  const ogImage = `/api/public/reports/${encodeURIComponent(token)}/og.jpg?v=${encodeURIComponent(report.og_version)}`;
  // The submission's own language, not the viewer's: a crawler has no locale
  // switcher to read, and the customer who shared this chose that language when
  // they created the check.
  const t = (report.language === "es" ? es : en).publicReport;
  const title = cardTitle(report);

  return {
    title,
    description: t.metaDescription,
    // A customer pasting a link into a Discord did not consent to being in
    // Google. Sharing is not publishing.
    robots: { index: false, follow: false },
    openGraph: {
      type: "article",
      siteName,
      title,
      description: t.metaDescription,
      // Absolute via `metadataBase` in app/layout.tsx -- messaging apps refuse
      // a relative one. Served with no auth, because that is the only kind of
      // fetch a crawler makes.
      //
      // 1200x630 is what every unfurler expects; stating it saves the crawler a
      // fetch to find out and stops some of them rendering a thumbnail.
      images: [{ url: ogImage, width: 1200, height: 630, alt: title }],
    },
    twitter: {
      card: "summary_large_image",
      title,
      description: t.metaDescription,
      images: [ogImage],
    },
  };
}

export default async function PublicReportPage({ params }: Props) {
  const { token } = await params;
  const report = await fetchPublicReport(token);
  // Unknown, rotated away, and no longer published all arrive here identically.
  if (!report) notFound();

  return <PublicReport report={report} shareToken={token} />;
}
