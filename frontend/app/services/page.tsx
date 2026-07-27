import type { Metadata } from "next";
import ServicesClient from "./services-client";

export const metadata: Metadata = {
  title: "Services",
  description:
    "Free card analysis and reports, an unlimited subscription, personalised pre-grading, restorations, pre-packaging for grading, and a local collection point in Gibraltar.",
};

export default function ServicesPage() {
  return <ServicesClient />;
}
