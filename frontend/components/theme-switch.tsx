"use client";

import { useEffect, useState } from "react";
import { useTheme } from "next-themes";
import { Switch } from "@heroui/react";

export default function ThemeSwitch() {
  const { resolvedTheme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted) {
    return <div className="h-6 w-11" aria-hidden="true" />;
  }

  const isDark = resolvedTheme === "dark";

  return (
    <Switch.Root
      aria-label="Toggle dark mode"
      isSelected={isDark}
      onChange={(selected) => setTheme(selected ? "dark" : "light")}
      size="sm"
    >
      {/* The switch itself is 32x16, which is the size it should look. The
          padding takes the *target* to 28px tall and the negative margin gives
          the space back, so the control is unchanged on screen and nothing
          around it moves -- the same trade the drag handles make, and the same
          one the nav links make with `-my-2 py-2`.

          Worth measuring rather than eyeballing: the underlying <input> reports
          13x13 because it sits hidden behind this label, so an audit that reads
          the input instead of the visible control gets a number that means
          nothing. */}
      <Switch.Content className="-my-1.5 py-1.5">
        <Switch.Control>
          <Switch.Thumb />
        </Switch.Control>
      </Switch.Content>
    </Switch.Root>
  );
}
