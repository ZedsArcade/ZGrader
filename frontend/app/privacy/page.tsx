import type { Metadata } from "next";
import PrivacyClient from "./privacy-client";
import { getServerBusinessName } from "@/lib/branding-server";

export async function generateMetadata(): Promise<Metadata> {
  const businessName = await getServerBusinessName();
  return {
    title: "Privacy Policy",
    description: `What personal data ${businessName} collects, why, how long it is kept, and your rights over it.`,
  };
}

export default function PrivacyPage() {
  return <PrivacyClient />;
}
