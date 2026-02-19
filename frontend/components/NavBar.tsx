"use client";

import Link from "next/link";
import { useAuthStore } from "@/store/authStore";
import UserMenu from "@/components/UserMenu";

const navItems = [
  { href: "/library", label: "Library" },
  { href: "/upload", label: "Upload CV" },
  { href: "/apply", label: "New Application" },
  { href: "/settings", label: "Settings" },
];

export default function NavBar() {
  const { user, initializing } = useAuthStore();

  return (
    <nav className="border-b bg-white">
      <div className="mx-auto flex h-14 max-w-7xl items-center gap-6 px-4">
        <Link href={user ? "/library" : "/login"} className="text-lg font-semibold">
          CV Tailor
        </Link>
        {!initializing && user && (
          <>
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
          </>
        )}
      </div>
    </nav>
  );
}
