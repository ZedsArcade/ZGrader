import type { Metadata } from "next";
import AboutClient from "./about-client";
import { getServerBusinessName } from "@/lib/branding-server";

// The copy lives in a client component because it comes from useTranslations();
// metadata can only be exported from a server component, hence the split.
// Same pattern as app/verify/[token]/page.tsx.
//
// generateMetadata rather than a static `metadata` object so the description
// names the operator's configured business, not a hardcoded one.
export async function generateMetadata(): Promise<Metadata> {
  const businessName = await getServerBusinessName();
  return {
    title: "About us",
    description: `${businessName} is an independent pre-grading service run from Gibraltar by a collector, for collectors.`,
  };
}

export default function AboutPage() {
  return <AboutClient />;
}
