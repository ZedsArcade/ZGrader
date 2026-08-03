import type { Metadata } from "next";
import CareServicesClient from "./care-services-client";
import { getServerCareBusinessName } from "@/lib/branding-server";

// Title composes with the care section's template (see app/care/layout.tsx),
// so this renders "Services | <care brand>" rather than picking up the
// analysis brand from the root layout.
export async function generateMetadata(): Promise<Metadata> {
  const careName = await getServerCareBusinessName();
  return {
    title: "Services",
    description: `Card care from ${careName}: handling and storage advice, surface cleaning, restoration consultations, and getting a card safely to a grading company.`,
  };
}

export default function CareServicesPage() {
  return <CareServicesClient />;
}
