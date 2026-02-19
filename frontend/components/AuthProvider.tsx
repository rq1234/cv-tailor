"use client";

import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useAuthStore } from "@/store/authStore";

const PUBLIC_ROUTES = new Set(["/login"]);

export default function AuthProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  // Use initializing (not loading) so auth operations like changePassword
  // don't replace the entire page with a loading screen.
  const { user, initializing, initialize, signupEmail } = useAuthStore();

  useEffect(() => {
    initialize();
  }, [initialize]);

  useEffect(() => {
    if (initializing) return;
    if (!user && !PUBLIC_ROUTES.has(pathname)) {
      router.replace("/login");
    } else if (user && PUBLIC_ROUTES.has(pathname) && !signupEmail) {
      // Don't redirect to library while waiting for email confirmation
      router.replace("/library");
    }
  }, [initializing, user, pathname, router, signupEmail]);

  if (initializing) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="text-sm text-muted-foreground">Loading...</div>
      </div>
    );
  }

  return <>{children}</>;
}
