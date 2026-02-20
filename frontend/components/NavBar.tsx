"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuthStore } from "@/store/authStore";
import UserMenu from "@/components/UserMenu";

const navItems = [
  { href: "/apply", label: "New Application" },
  { href: "/applications", label: "Applications" },
  { href: "/library", label: "Library" },
  { href: "/upload", label: "Add / Update CV" },
  { href: "/settings", label: "Settings" },
];

export default function NavBar() {
  const { user, initializing } = useAuthStore();
  const pathname = usePathname();

  return (
    <nav className="border-b bg-white">
      <div className="mx-auto flex h-14 max-w-7xl items-center gap-6 px-4">
        <Link href={user ? "/library" : "/"} className="text-lg font-semibold">
          CV Tailor
        </Link>
        {!initializing && user && (
          <>
            <div className="flex gap-4">
              {navItems.map((item) => {
                const isActive = pathname === item.href || pathname.startsWith(item.href + "/");
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
            <UserMenu />
          </>
        )}
      </div>
    </nav>
  );
}
