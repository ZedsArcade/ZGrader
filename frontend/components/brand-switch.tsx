"use client";

import { useRouter } from "next/navigation";
import { ButtonGroup } from "@heroui/react";
import Button from "@/components/Button";
import { useBranding } from "@/lib/branding-context";
import { CARE_PREFIX, storeBrand, type Brand } from "@/lib/brand";
import { useBrand } from "@/lib/use-brand";

/**
 * Switches between the two public sections.
 *
 * Shaped like LocaleSwitch and ThemeSwitch so the header reads as one set of
 * controls. Unlike those two it also changes the route, because each brand has
 * its own landing page -- but it persists the choice as well, so leaving for a
 * page both brands share (About, Services, the dashboard) keeps the palette
 * you picked.
 *
 * Both names come from Settings, so renaming either in admin renames it here.
 */
export default function BrandSwitch() {
  const router = useRouter();
  const { business_name, care_business_name } = useBranding();
  const brand = useBrand();

  function select(next: Brand) {
    // Persisted before navigating so the destination resolves to the new
    // brand on arrival rather than reading the previous one for a frame.
    storeBrand(next);
    router.push(next === "care" ? CARE_PREFIX : "/");
  }

  return (
    <ButtonGroup size="sm">
      <Button
        variant={brand === "lab" ? "primary" : "outline"}
        onPress={() => select("lab")}
        aria-pressed={brand === "lab"}
        className="whitespace-nowrap"
      >
        {business_name}
      </Button>
      <Button
        variant={brand === "care" ? "primary" : "outline"}
        onPress={() => select("care")}
        aria-pressed={brand === "care"}
        className="whitespace-nowrap"
      >
        {care_business_name}
      </Button>
    </ButtonGroup>
  );
}
