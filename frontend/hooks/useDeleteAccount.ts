"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { useAuthStore } from "@/store/authStore";

export function useDeleteAccount() {
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { signOut } = useAuthStore();
  const router = useRouter();

  const deleteAccount = async () => {
    setDeleting(true);
    setError(null);
    try {
      await api.delete("/api/account");
      await signOut();
      router.push("/login");
    } catch {
      setError("Failed to delete account. Please try again.");
      setDeleting(false);
    }
  };

  return { deleting, error, deleteAccount };
}
