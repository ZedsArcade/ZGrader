import type { Metadata } from "next";
import PrivacyClient from "./privacy-client";

export const metadata: Metadata = {
  title: "Privacy Policy",
  description:
    "What personal data Card Care Center collects, why, how long it is kept, and your rights over it.",
};

export default function PrivacyPage() {
  return <PrivacyClient />;
}
