import type { MetadataRoute } from "next";

/**
 * Said twice on purpose.
 *
 * Every shared report already carries `robots: noindex, nofollow` in its own
 * metadata, which is the directive that actually binds a crawler that fetched
 * the page. This disallow keeps well-behaved crawlers from requesting `/r/*` at
 * all -- cheaper for an origin that is a home server, and a second statement of
 * the same intent for anything that reads robots.txt but not meta tags.
 *
 * A customer pasting a link into a Discord did not consent to being in Google.
 * Sharing is not publishing.
 */
export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      {
        userAgent: "*",
        disallow: ["/r/", "/api/", "/dashboard/", "/admin/", "/account"],
      },
    ],
  };
}
