"use client";

import Link from "next/link";
import * as api from "@/lib/api";
import { useBranding } from "@/lib/branding-context";
import { CARE_PREFIX } from "@/lib/brand";
import { useBrand } from "@/lib/use-brand";
import { useBrandLogos } from "@/lib/use-brand-logos";

/**
 * The active brand's logo, linking to that brand's home.
 *
 * Renders nothing at all when no logo has been uploaded. The section switch
 * beside it already carries the identity, so an operator who hasn't set one
 * gets a clean header rather than a placeholder or a broken image.
 *
 * Height is fixed and width is left to the image so a wide or a square logo
 * both sit correctly in the bar, with a max width to stop an extreme aspect
 * ratio pushing the navigation off the end.
 */
export default function BrandLogo() {
  const brand = useBrand();
  const { business_name, care_business_name } = useBranding();
  const { logos } = useBrandLogos();

  const version = logos[brand];
  if (version === undefined) return null;

  const name = brand === "care" ? care_business_name : business_name;

  return (
    <Link href={brand === "care" ? CARE_PREFIX : "/"} className="shrink-0">
      {/* Plain <img>: the source is an operator upload behind a versioned API
          URL, not a build-time asset, so next/image's optimiser would add a
          round trip for no benefit here. */}
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={api.brandLogoUrl(brand, version)}
        alt={name}
        className="h-9 w-auto max-w-40 object-contain"
      />
    </Link>
  );
}
