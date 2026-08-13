import type { Metadata } from "next";
import PricingClient from "./pricing-client";

export const metadata: Metadata = {
  title: "Pricing",
  description:
    "What a pre-grading check costs: free image analysis from your own photos, paid tiers for regular use, and per-card pricing for an in-hand pre-grade.",
};

export default function PricingPage() {
  return <PricingClient />;
}
