import type { Metadata } from "next";
import "./globals.css";
import { AuthProvider } from "@/lib/auth-context";
import { BrandingProvider } from "@/lib/branding-context";
import NavBar from "@/components/NavBar";

export const metadata: Metadata = {
  title: "ZGrader",
  description: "Independent TCG card pre-grading service",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>
        <BrandingProvider>
          <AuthProvider>
            <NavBar />
            <main>{children}</main>
          </AuthProvider>
        </BrandingProvider>
      </body>
    </html>
  );
}
