import type { Metadata } from "next";
import { Toast } from "@heroui/react";
import "./globals.css";
import { Providers } from "./providers";
import { AuthProvider } from "@/lib/auth-context";
import { BrandingProvider } from "@/lib/branding-context";
import { getServerBusinessName } from "@/lib/branding-server";
import { LocaleProvider } from "@/lib/i18n/context";
import Footer from "@/components/Footer";
import NavBar from "@/components/NavBar";

const SITE_DESCRIPTION =
  "Independent pre-grading for trading card games. Check centering, corners, edges and surface before you pay to submit a card for grading.";

// The site name follows the operator's configured business_name, the same
// value NavBar and Footer render, so renaming the business in admin also
// renames the browser tab and every social link preview. It has to be fetched
// server-side here: `metadata` is a server-component export and cannot read
// the client-side branding context. See lib/branding-server.ts for why this
// needs a revalidation window rather than plain static generation.
//
// metadataBase makes the relative OG image below resolve to an absolute URL,
// which is what social and messaging apps require when they unfurl a link.
// NEXT_PUBLIC_SITE_URL lets a deployment point it at its real domain.
export async function generateMetadata(): Promise<Metadata> {
  const siteName = await getServerBusinessName();
  return {
    metadataBase: new URL(process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000"),
    title: { default: siteName, template: `%s | ${siteName}` },
    description: SITE_DESCRIPTION,
    openGraph: {
      type: "website",
      siteName,
      title: siteName,
      description: SITE_DESCRIPTION,
      images: [{ url: "/og.png", width: 1200, height: 630, alt: siteName }],
    },
    twitter: {
      card: "summary_large_image",
      title: siteName,
      description: SITE_DESCRIPTION,
      images: ["/og.png"],
    },
  };
}

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
                <Footer />
                <Toast.Provider />
              </AuthProvider>
            </BrandingProvider>
          </LocaleProvider>
        </Providers>
      </body>
    </html>
  );
}
