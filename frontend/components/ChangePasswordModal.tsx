"use client";

import { useState } from "react";
import { useAuthStore } from "@/store/authStore";

interface ChangePasswordModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function ChangePasswordModal({ isOpen, onClose }: ChangePasswordModalProps) {
  const { changePassword, loading, error } = useAuthStore();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [localError, setLocalError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLocalError(null);
    setSuccess(false);

    // Validate
    if (!currentPassword || !newPassword || !confirmPassword) {
      setLocalError("Please fill in all fields");
      return;
    }

    if (newPassword.length < 8) {
      setLocalError("Password must be at least 8 characters");
      return;
    }

    if (newPassword !== confirmPassword) {
      setLocalError("Passwords do not match");
      return;
    }

    if (newPassword === currentPassword) {
      setLocalError("New password must be different from current password");
      return;
    }

    // Change password — verifies current password via re-authentication
    const success = await changePassword(currentPassword, newPassword);
    if (success) {
      setSuccess(true);
      setTimeout(() => {
        resetForm();
        onClose();
      }, 2000);
    }
  };

  const resetForm = () => {
    setCurrentPassword("");
    setNewPassword("");
    setConfirmPassword("");
    setLocalError(null);
    setSuccess(false);
  };

  const handleClose = () => {
    resetForm();
    onClose();
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 max-w-md w-full mx-4">
        <h2 className="text-xl font-semibold mb-4">Change Password</h2>

        {success ? (
          <div className="rounded-md bg-green-50 px-3 py-2 text-sm text-green-700">
            Password changed successfully!
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-1">Current Password</label>
              <input
                type="password"
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                className="w-full rounded-md border px-3 py-2 text-sm"
                placeholder="••••••••"
                disabled={loading}
              />
              <p className="text-xs text-muted-foreground mt-1">
                (For security, confirm your current password)
              </p>
            </div>

            <div>
              <label className="block text-sm font-medium mb-1">New Password</label>
              <input
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                className="w-full rounded-md border px-3 py-2 text-sm"
                placeholder="••••••••"
                disabled={loading}
              />
              <p className="text-xs text-muted-foreground mt-1">Minimum 8 characters</p>
            </div>

            <div>
              <label className="block text-sm font-medium mb-1">Confirm New Password</label>
              <input
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                className="w-full rounded-md border px-3 py-2 text-sm"
                placeholder="••••••••"
                disabled={loading}
              />
            </div>

            {(localError || error) && (
              <div className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
                {localError || error}
              </div>
            )}

            <div className="flex gap-2 pt-4">
              <button
                type="button"
                onClick={handleClose}
                className="flex-1 rounded-md border px-3 py-2 text-sm font-medium hover:bg-gray-50"
                disabled={loading}
              >
                Cancel
              </button>
              <button
                type="submit"
                className="flex-1 rounded-md bg-black px-3 py-2 text-sm font-medium text-white hover:bg-black/90 disabled:bg-gray-400"
                disabled={loading}
              >
                {loading ? "Updating..." : "Change Password"}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
