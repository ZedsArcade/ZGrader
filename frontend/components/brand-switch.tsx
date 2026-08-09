"use client";

import { useRouter } from "next/navigation";
import { ButtonGroup } from "@heroui/react";
import Button from "@/components/Button";
import { useBranding } from "@/lib/branding-context";
import { CARE_PREFIX, storeBrand, type Brand } from "@/lib/brand";
import { sweepBrandChange } from "@/lib/brand-transition";
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

    // Only sweep when the palette is actually changing. Pressing the button
    // for the brand you are already in still navigates home -- that is what it
    // did before and what the header's other controls do -- but animating a
    // repaint that produces identical pixels just looks like a glitch.
    if (next !== brand) {
      // The wave finishes where the pressed button is: GemCare sits on the
      // right of the group, so selecting it sweeps left-to-right, and
      // selecting GemLab runs the other way. The motion then matches the
      // direction the eye just travelled.
      sweepBrandChange(next === "care" ? "ltr" : "rtl", () => {
        // Synchronous and deliberately narrow: the view transition snapshots
        // either side of this callback, so the palette flip is the only thing
        // that ends up inside the animation. The router push below lands
        // outside it, which is what keeps the wave about colour rather than
        // half-animating a route change.
        document.documentElement.setAttribute("data-brand", next);
      });
    }

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
