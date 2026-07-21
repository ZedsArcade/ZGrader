"use client";

import { useEffect, useState } from "react";
import { Button, ButtonGroup } from "@heroui/react";
import { useLocale, type Locale } from "@/lib/i18n/context";

export default function LocaleSwitch() {
  const { locale, setLocale } = useLocale();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted) {
    return <div className="h-8 w-[76px]" aria-hidden="true" />;
  }

  function select(next: Locale) {
    setLocale(next);
  }

  return (
    <ButtonGroup size="sm">
      <Button
        variant={locale === "en" ? "primary" : "outline"}
        onPress={() => select("en")}
        aria-pressed={locale === "en"}
      >
        EN
      </Button>
      <Button
        variant={locale === "es" ? "primary" : "outline"}
        onPress={() => select("es")}
        aria-pressed={locale === "es"}
      >
        ES
      </Button>
    </ButtonGroup>
  );
}
