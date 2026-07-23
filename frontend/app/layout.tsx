import type { Metadata } from "next";
import { Toast } from "@heroui/react";
import "./globals.css";
import { Providers } from "./providers";
import { AuthProvider } from "@/lib/auth-context";
import { BrandingProvider } from "@/lib/branding-context";
import { LocaleProvider } from "@/lib/i18n/context";
import NavBar from "@/components/NavBar";

export const metadata: Metadata = {
  title: "Card Care Center",
  description: "Independent TCG card pre-grading service",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="min-h-screen flex flex-col bg-background text-foreground font-sans antialiased">
        <Providers themeProps={{ attribute: "class", defaultTheme: "system", enableSystem: true }}>
          <LocaleProvider>
            <BrandingProvider>
              <AuthProvider>
                <NavBar />
                <main className="mx-auto w-full max-w-5xl flex-1 px-5 py-8 pb-16">{children}</main>
                <Toast.Provider />
              </AuthProvider>
            </BrandingProvider>
          </LocaleProvider>
        </Providers>
      </body>
    </html>
  );
}
