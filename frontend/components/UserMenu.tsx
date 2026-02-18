"use client";

import { useRouter } from "next/navigation";
import { useAuthStore } from "@/store/authStore";

export default function UserMenu() {
  const router = useRouter();
  const { user, signOut, loading } = useAuthStore();

  if (!user) return null;

  const handleSignOut = async () => {
    await signOut();
    router.replace("/login");
  };

  return (
    <div className="ml-auto flex items-center gap-3 text-sm">
      <span className="text-muted-foreground">{user.email}</span>
      <button
        type="button"
        onClick={handleSignOut}
        disabled={loading}
        className="rounded-md border px-2.5 py-1 text-xs hover:bg-muted"
      >
        Sign out
      </button>
    </div>
  );
}
