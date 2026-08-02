import type { Metadata } from "next";
import CareClient from "./care-client";
import { getServerCareBusinessName } from "@/lib/branding-server";

// No `title` here on purpose: app/care/layout.tsx sets the section default,
// so setting one again would render "GemCare | GemCare".
//
// The description names the care brand rather than the analysis one, which is
// the payoff of deriving the brand from the route -- the server knows which
// section a page belongs to without any client-side state.
export async function generateMetadata(): Promise<Metadata> {
  const careName = await getServerCareBusinessName();
  return {
    description: `${careName} is the card-care side of the service: handling, storage, surface cleaning, and honest advice on what restoration can and cannot safely achieve.`,
  };
}

export default function CarePage() {
  return <CareClient />;
}
