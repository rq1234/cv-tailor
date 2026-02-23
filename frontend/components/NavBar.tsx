"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuthStore } from "@/store/authStore";
import UserMenu from "@/components/UserMenu";
import { Menu, X } from "lucide-react";

const navItems = [
  { href: "/applications", label: "Applications" },
  { href: "/apply", label: "New Application" },
  { href: "/library", label: "CV Library" },
  { href: "/upload", label: "Upload" },
  { href: "/settings", label: "Settings" },
];

export default function NavBar() {
  const { user, initializing } = useAuthStore();
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <nav className="border-b bg-white">
      <div className="mx-auto flex h-14 max-w-7xl items-center justify-between px-4">
        {/* Left: logo + desktop nav */}
        <div className="flex items-center gap-6">
          <Link
            href={user ? "/applications" : "/"}
            className="text-lg font-semibold"
            onClick={() => setMobileOpen(false)}
          >
            CV Tailor
          </Link>
          {!initializing && user && (
            <div className="hidden md:flex gap-4">
              {navItems.map((item) => {
                const isActive =
                  pathname === item.href || pathname.startsWith(item.href + "/");
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={`text-sm transition-colors ${
                      isActive
                        ? "font-medium text-foreground"
                        : "text-muted-foreground hover:text-foreground"
                    }`}
                  >
                    {item.label}
                  </Link>
                );
              })}
            </div>
          )}
        </div>

        {/* Right: user menu + hamburger */}
        {!initializing && user && (
          <div className="flex items-center gap-2">
            <UserMenu />
            <button
              className="md:hidden p-1 text-muted-foreground hover:text-foreground"
              onClick={() => setMobileOpen((o) => !o)}
              aria-label="Toggle navigation menu"
            >
              {mobileOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
            </button>
          </div>
        )}
      </div>

      {/* Mobile dropdown menu */}
      {!initializing && user && mobileOpen && (
        <div className="border-t md:hidden">
          <div className="flex flex-col px-4 py-1">
            {navItems.map((item) => {
              const isActive =
                pathname === item.href || pathname.startsWith(item.href + "/");
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={() => setMobileOpen(false)}
                  className={`border-b py-3 text-sm transition-colors last:border-0 ${
                    isActive
                      ? "font-medium text-foreground"
                      : "text-muted-foreground hover:text-foreground"
                  }`}
                >
                  {item.label}
                </Link>
              );
            })}
          </div>
        </div>
      )}
    </nav>
  );
}
