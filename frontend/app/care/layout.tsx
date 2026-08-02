import type { Metadata } from "next";
import { getServerCareBusinessName } from "@/lib/branding-server";

/**
 * Gives the care section its own title template.
 *
 * Without this the root layout's `%s | <analysis brand>` template applies
 * here too, so a GemCare page renders "GemCare | GemLab" -- the wrong brand
 * in the browser tab and in every link preview. Overriding the template at
 * the section boundary is what makes the two sides read as separate sites.
 *
 * `absolute` rather than `default` is load-bearing. A parent template applies
 * to any title a child segment sets, so `default` alone still came out as
 * "GemCare | <analysis brand>"; `absolute` is the documented way to opt out
 * of the inherited template, while `template` here still supplies one to the
 * section's own child pages.
 *
 * Layout only sets metadata; it deliberately renders nothing around
 * `children`. The nav, footer and theming all live in the root layout and
 * follow the route via data-brand (see lib/brand.ts), so there is no
 * per-section chrome to add here.
 */
export async function generateMetadata(): Promise<Metadata> {
  const careName = await getServerCareBusinessName();
  return {
    title: { absolute: careName, template: `%s | ${careName}` },
  };
}

export default function CareLayout({ children }: { children: React.ReactNode }) {
  return children;
}
