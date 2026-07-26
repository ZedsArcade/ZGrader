import type { Metadata } from "next";
import TermsClient from "./terms-client";

export const metadata: Metadata = {
  title: "Terms & Conditions",
  description:
    "The terms covering use of Card Care Center, including what our pre-grading estimate is and is not.",
};

export default function TermsPage() {
  return <TermsClient />;
}
