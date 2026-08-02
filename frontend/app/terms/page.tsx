import type { Metadata } from "next";
import TermsClient from "./terms-client";
import { getServerBusinessName } from "@/lib/branding-server";

export async function generateMetadata(): Promise<Metadata> {
  const businessName = await getServerBusinessName();
  return {
    title: "Terms & Conditions",
    description: `The terms covering use of ${businessName}, including what our pre-grading estimate is and is not.`,
  };
}

export default function TermsPage() {
  return <TermsClient />;
}
