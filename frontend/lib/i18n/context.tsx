"use client";

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { en, type Dictionary } from "./en";
import { es } from "./es";

export type Locale = "en" | "es";

const DICTIONARIES: Record<Locale, Dictionary> = { en, es };
const STORAGE_KEY = "zgrader_locale";

export function getDictionary(locale: Locale): Dictionary {
  return DICTIONARIES[locale];
}

interface LocaleContextValue {
  locale: Locale;
  setLocale: (locale: Locale) => void;
}

const LocaleContext = createContext<LocaleContextValue>({
  locale: "en",
  setLocale: () => {},
});

export function LocaleProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>("en");

  useEffect(() => {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (stored === "en" || stored === "es") {
      setLocaleState(stored);
    }
  }, []);

  function setLocale(next: Locale) {
    window.localStorage.setItem(STORAGE_KEY, next);
    setLocaleState(next);
  }

  return <LocaleContext.Provider value={{ locale, setLocale }}>{children}</LocaleContext.Provider>;
}

export function useLocale(): LocaleContextValue {
  return useContext(LocaleContext);
}

export function useTranslations(): Dictionary {
  const { locale } = useLocale();
  return DICTIONARIES[locale];
}
