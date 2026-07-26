import type { Metadata } from "next";
import HowItWorksClient from "./how-it-works-client";

export const metadata: Metadata = {
  title: "How it works",
  description:
    "Create a submission, add a photo or send the card, let the analysis run, and read a report covering centering, corners, edges and surface.",
};

export default function HowItWorksPage() {
  return <HowItWorksClient />;
}
