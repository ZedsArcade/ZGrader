import type { Metadata } from "next";
import MethodologyClient from "./methodology-client";

export const metadata: Metadata = {
  title: "How the analysis works",
  description:
    "What the automated card analysis measures, how it decides, and where it gets things wrong -- illustrated with real output from the detector itself.",
};

export default function MethodologyPage() {
  return <MethodologyClient />;
}
