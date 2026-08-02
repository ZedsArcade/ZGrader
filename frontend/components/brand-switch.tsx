"use client";

import { usePathname, useRouter } from "next/navigation";
import { ButtonGroup } from "@heroui/react";
import Button from "@/components/Button";
import { useBranding } from "@/lib/branding-context";
import { brandFromPathname, CARE_PREFIX } from "@/lib/brand";

/**
 * Switches between the two public sections.
 *
 * Shaped like LocaleSwitch and ThemeSwitch so the header reads as one set of
 * controls, but unlike those two this changes the route rather than a stored
 * preference -- the brand is derived from the URL (see lib/brand.ts). Both
 * names come from Settings, so an operator renaming either one in admin
 * renames it here.
 *
 * No mounted-guard is needed: unlike locale and theme, nothing here is read
 * from localStorage, so the server and the client agree on first render.
 */
export default function BrandSwitch() {
  const pathname = usePathname() ?? "/";
  const router = useRouter();
  const { business_name, care_business_name } = useBranding();
  const brand = brandFromPathname(pathname);

  return (
    <ButtonGroup size="sm">
      <Button
        variant={brand === "lab" ? "primary" : "outline"}
        onPress={() => router.push("/")}
        aria-pressed={brand === "lab"}
      >
        {business_name}
      </Button>
      <Button
        variant={brand === "care" ? "primary" : "outline"}
        onPress={() => router.push(CARE_PREFIX)}
        aria-pressed={brand === "care"}
      >
        {care_business_name}
      </Button>
    </ButtonGroup>
  );
}
