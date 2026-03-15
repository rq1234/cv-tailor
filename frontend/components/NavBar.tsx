"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuthStore } from "@/store/authStore";
import { useAppStore } from "@/store/appStore";
import UserMenu from "@/components/UserMenu";
import { Menu, X, Sparkles, Plus } from "lucide-react";

const navItems = [
  { href: "/applications", label: "Applications" },
  { href: "/library", label: "CV Library" },
  { href: "/upload", label: "Upload" },
  { href: "/settings", label: "Settings" },
];

export default function NavBar() {
  const { user, initializing } = useAuthStore();
  const { pipeline } = useAppStore();
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);
  const pipelineRunning = pipeline !== null && pipeline.status === "running";

  return (
    <nav className="sticky top-0 z-50 border-b bg-white/95 backdrop-blur-sm">
      <div className="mx-auto flex h-14 max-w-7xl items-center justify-between px-4">
        {/* Left: logo + desktop nav */}
        <div className="flex items-center gap-6">
          <Link
            href={user ? "/applications" : "/"}
            className="flex items-center gap-2"
            onClick={() => setMobileOpen(false)}
          >
            <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-blue-600">
              <Sparkles className="h-4 w-4 text-white" />
            </div>
            <span className="text-base font-bold text-slate-900">CV Tailor</span>
          </Link>
          {!initializing && user && (
            <div className="hidden md:flex gap-1">
              {navItems.map((item) => {
                const isActive =
                  pathname === item.href || pathname.startsWith(item.href + "/");
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={`relative rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
                      isActive
                        ? "text-blue-600 bg-blue-50"
                        : "text-slate-600 hover:text-slate-900 hover:bg-slate-100"
                    }`}
                  >
                    {item.label}
                    {isActive && (
                      <span className="absolute bottom-0 left-3 right-3 h-0.5 rounded-full bg-blue-600" />
                    )}
                  </Link>
                );
              })}
            </div>
          )}
        </div>

        {/* Right: pipeline indicator + new app shortcut + user menu + hamburger */}
        {!initializing && user && (
          <div className="flex items-center gap-2">
            {pipelineRunning && (
              <Link
                href="/apply"
                className="hidden sm:inline-flex items-center gap-1.5 rounded-full bg-blue-50 border border-blue-200 px-2.5 py-1 text-xs font-medium text-blue-700 hover:bg-blue-100 transition-colors"
                title="Tailoring in progress — click to view"
              >
                <span className="h-1.5 w-1.5 rounded-full bg-blue-500 animate-pulse" />
                Generating…
              </Link>
            )}
            <Link
              href="/apply"
              className="hidden sm:inline-flex items-center gap-1 rounded-md border px-2.5 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-100 hover:text-slate-900 transition-colors"
              title="New Application"
            >
              <Plus className="h-3.5 w-3.5" /> New Application
            </Link>
            <UserMenu />
            <button
              className="md:hidden rounded-md p-1.5 text-slate-500 hover:text-slate-900 hover:bg-slate-100 transition-colors"
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
        <div className="border-t md:hidden bg-white">
          <div className="flex flex-col px-3 py-2 gap-1">
            {navItems.map((item) => {
              const isActive =
                pathname === item.href || pathname.startsWith(item.href + "/");
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={() => setMobileOpen(false)}
                  className={`rounded-md px-3 py-2.5 text-sm font-medium transition-colors border-l-2 ${
                    isActive
                      ? "text-blue-600 bg-blue-50 border-blue-600"
                      : "text-slate-600 hover:text-slate-900 hover:bg-slate-100 border-transparent"
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
