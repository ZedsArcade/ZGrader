import type { Metadata } from "next";
import RefundsClient from "./refunds-client";
import { getServerBusinessName } from "@/lib/branding-server";

export async function generateMetadata(): Promise<Metadata> {
  const businessName = await getServerBusinessName();
  return {
    title: "Refund Policy",
    description: `When you can cancel a paid service from ${businessName}, when you can get your money back, and the point after which you cannot.`,
  };
}

export default function RefundsPage() {
  return <RefundsClient />;
}
