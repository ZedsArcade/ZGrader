"use client";

import type { ThemeProviderProps } from "next-themes";
import type { ReactNode } from "react";
import { ThemeProvider as NextThemesProvider } from "next-themes";

export function Providers({
  children,
  themeProps,
}: {
  children: ReactNode;
  themeProps?: ThemeProviderProps;
}) {
  return <NextThemesProvider {...themeProps}>{children}</NextThemesProvider>;
}
