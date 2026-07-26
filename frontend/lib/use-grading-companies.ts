"use client";

import { useBranding } from "./branding-context";
import { useLocale } from "./i18n/context";
import { getDictionary } from "./i18n/context";

/**
 * The enabled grading companies, formatted for use inside a sentence.
 *
 * `Intl.ListFormat` supplies the right conjunction per language -- "PSA, BGS
 * and CGC" in English, "PSA, BGS y CGC" in Spanish -- so the copy doesn't
 * need a hand-rolled joiner per locale.
 *
 * Returns a generic phrase when nothing is enabled, so an operator who turns
 * the whole comparison off still gets a sentence that reads properly rather
 * than one with a hole in it.
 */
export function useGradingCompanies(): string {
  const { grading_companies } = useBranding();
  const { locale } = useLocale();

  if (grading_companies.length === 0) {
    return getDictionary(locale).landing.companiesFallback;
  }
  return new Intl.ListFormat(locale, { style: "long", type: "conjunction" }).format(
    grading_companies
  );
}

/** Replaces the {companies} placeholder used by the marketing copy. */
export function withCompanies(text: string, companies: string): string {
  return text.replace("{companies}", companies);
}
