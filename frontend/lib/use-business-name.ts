"use client";

import { useBranding } from "./branding-context";

/**
 * The operator's configured business name, for use inside a sentence.
 *
 * Comes from the `settings` table via /catalog/branding, so renaming the
 * business in the admin panel updates the copy everywhere rather than leaving
 * the old name baked into the marketing and legal text. Falls back to the
 * shipped default while the branding request is in flight -- see
 * DEFAULT_BRANDING in branding-context.tsx.
 */
export function useBusinessName(): string {
  return useBranding().business_name;
}

/**
 * Replaces the {businessName} placeholder used throughout the copy.
 *
 * A global regex rather than String.replaceAll, which needs a newer lib target
 * than this project's copy helpers assume; several strings mention the
 * business more than once, so a plain .replace would only catch the first.
 */
export function withBusinessName(text: string, businessName: string): string {
  return text.replace(/\{businessName\}/g, businessName);
}
