import type { Metadata } from "next";
import localFont from "next/font/local";
import "./globals.css";
import AuthProvider from "@/components/AuthProvider";
import NavBar from "@/components/NavBar";

// This app is fully authenticated — disable static generation for all routes.
// Without this, Next.js tries to prerender pages at build time when
// NEXT_PUBLIC_SUPABASE_URL is not set, causing "supabaseUrl is required" errors.
export const dynamic = "force-dynamic";

const geistSans = localFont({
  src: "./fonts/GeistVF.woff",
  variable: "--font-geist-sans",
  weight: "100 900",
});
const geistMono = localFont({
  src: "./fonts/GeistMonoVF.woff",
  variable: "--font-geist-mono",
  weight: "100 900",
});

export const metadata: Metadata = {
  title: "CV Tailor",
  description: "AI-powered CV tailoring for job applications",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased min-h-screen bg-background`}
      >
        <AuthProvider>
          <NavBar />
          <main className="mx-auto max-w-7xl px-4 py-6">{children}</main>
        </AuthProvider>
      </body>
    </html>
  );
}
