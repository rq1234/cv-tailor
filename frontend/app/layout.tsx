import type { Metadata } from "next";
import localFont from "next/font/local";
import Link from "next/link";
import "./globals.css";
import AuthProvider from "@/components/AuthProvider";
import UserMenu from "@/components/UserMenu";

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

const navItems = [
  { href: "/library", label: "Library" },
  { href: "/upload", label: "Upload CV" },
  { href: "/apply", label: "New Application" },
  { href: "/settings", label: "Settings" },
];

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
          <nav className="border-b bg-white">
            <div className="mx-auto flex h-14 max-w-7xl items-center gap-6 px-4">
              <Link href="/library" className="text-lg font-semibold">
                CV Tailor
              </Link>
              <div className="flex gap-4">
                {navItems.map((item) => (
                  <Link
                    key={item.href}
                    href={item.href}
                    className="text-sm text-muted-foreground hover:text-foreground transition-colors"
                  >
                    {item.label}
                  </Link>
                ))}
              </div>
              <UserMenu />
            </div>
          </nav>
          <main className="mx-auto max-w-7xl px-4 py-6">{children}</main>
        </AuthProvider>
      </body>
    </html>
  );
}
