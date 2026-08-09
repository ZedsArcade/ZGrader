"use client";

import Link from "next/link";
import type { ComponentProps } from "react";
import { storeBrand, type Brand } from "@/lib/brand";

/**
 * A link that hands the visitor over to the *other* brand.
 *
 * Only /care/* forces a brand (see lib/brand.ts). Every other route belongs to
 * both, so `resolveBrand` falls through to the stored preference -- which means
 * a plain <Link href="/services"> clicked from GemCare lands on GemLab's
 * services page still wearing GemCare's palette. That is the bug this exists to
 * prevent: the destination brand has to be recorded *before* the navigation, or
 * BrandSync resolves the old preference on arrival and nothing changes.
 *
 * Note this is only needed for links pointing at a route both brands share.
 * A link into /care/* is already unambiguous and needs no help.
 *
 * `onNavigate` rather than `onClick` is deliberate: it fires only for same-tab
 * client navigation, so Cmd/Ctrl-clicking to open the other brand in a new tab
 * doesn't silently reassign the brand of the tab you are still looking at.
 */
export default function BrandLink({
  brand,
  ...props
}: { brand: Brand } & Omit<ComponentProps<typeof Link>, "onNavigate">) {
  return <Link {...props} onNavigate={() => storeBrand(brand)} />;
}
