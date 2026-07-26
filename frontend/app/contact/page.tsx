import type { Metadata } from "next";
import ContactClient from "./contact-client";

export const metadata: Metadata = {
  title: "Contact",
  description:
    "Get in touch about a card, a restoration consultation, or any of our services. Based in Gibraltar.",
};

export default function ContactPage() {
  return <ContactClient />;
}
