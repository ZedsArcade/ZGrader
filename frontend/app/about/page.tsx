import type { Metadata } from "next";
import AboutClient from "./about-client";

// The copy lives in a client component because it comes from useTranslations();
// `metadata` can only be exported from a server component, hence the split.
// Same pattern as app/verify/[token]/page.tsx.
export const metadata: Metadata = {
  title: "About us",
  description:
    "Card Care Center is an independent pre-grading service run from Gibraltar by a collector, for collectors.",
};

export default function AboutPage() {
  return <AboutClient />;
}
