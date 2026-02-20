"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuthStore } from "@/store/authStore";
import { api } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { signIn, signUp, resetPassword, resendConfirmation, loading, error, signupEmail, clearSignupEmail, user, initializing } = useAuthStore();

  const redirectAfterAuth = useCallback(async () => {
    try {
      const pool = await api.get<{ work_experiences: unknown[]; education: unknown[]; projects: unknown[]; activities: unknown[]; skills: unknown[] }>("/api/cv/pool");
      const hasContent =
        pool.work_experiences.length > 0 ||
        pool.education.length > 0 ||
        pool.projects.length > 0 ||
        pool.activities.length > 0 ||
        pool.skills.length > 0;
      router.replace(hasContent ? "/library" : "/upload");
    } catch {
      router.replace("/library");
    }
  }, [router]);

  // If already authenticated (and not waiting for email confirmation), redirect away
  useEffect(() => {
    if (!initializing && user && !signupEmail) {
      redirectAfterAuth();
    }
  }, [user, initializing, signupEmail, redirectAfterAuth]);

  const initialMode = searchParams.get("mode") === "signup" ? "signup" : "signin";
  const [mode, setMode] = useState<"signin" | "signup" | "forgot">(initialMode);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [localError, setLocalError] = useState<string | null>(null);
  const [resetSent, setResetSent] = useState(false);
  const [resendSent, setResendSent] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLocalError(null);

    if (mode === "forgot") {
      if (!email) { setLocalError("Enter your email address."); return; }
      const ok = await resetPassword(email);
      if (ok) setResetSent(true);
      return;
    }

    if (!email || !password) {
      setLocalError("Email and password are required.");
      return;
    }

    if (mode === "signup" && password.length < 8) {
      setLocalError("Password must be at least 8 characters.");
      return;
    }

    if (mode === "signup" && password !== confirmPassword) {
      setLocalError("Passwords do not match.");
      return;
    }

    if (mode === "signin") {
      const success = await signIn(email, password);
      if (success) {
        await redirectAfterAuth();
      }
    } else {
      await signUp(email, password);
    }
  };

  const switchMode = (next: "signin" | "signup" | "forgot") => {
    setMode(next);
    setPassword("");
    setConfirmPassword("");
    setLocalError(null);
    setResetSent(false);
  };

  return (
    <div className="mx-auto flex min-h-[80vh] max-w-md items-center">
      <div className="w-full rounded-lg border bg-white p-6 shadow-sm">

        {/* ── Confirm email screen ── */}
        {signupEmail ? (
          <>
            <h1 className="text-xl font-semibold">Check your email</h1>
            <p className="mt-1 text-sm text-muted-foreground">
              We sent a confirmation link to <strong>{signupEmail}</strong>
            </p>
            <div className="mt-4 rounded-md bg-blue-50 px-3 py-2 text-sm text-blue-700">
              Click the link in your email to verify your account, then sign in.
            </div>

            {resendSent ? (
              <p className="mt-4 text-sm text-green-700">Email resent! Check your inbox.</p>
            ) : (
              <button
                onClick={async () => {
                  const ok = await resendConfirmation(signupEmail);
                  if (ok) setResendSent(true);
                }}
                disabled={loading}
                className="mt-4 w-full rounded-md border px-3 py-2 text-sm font-medium hover:bg-muted disabled:opacity-50"
              >
                {loading ? "Sending..." : "Resend confirmation email"}
              </button>
            )}

            <button
              onClick={() => { clearSignupEmail(); switchMode("signin"); setEmail(""); }}
              className="mt-2 w-full rounded-md bg-black px-3 py-2 text-sm font-medium text-white hover:bg-black/90"
            >
              Back to Sign In
            </button>
          </>

        /* ── Forgot password screen ── */
        ) : mode === "forgot" ? (
          <>
            <h1 className="text-xl font-semibold">Reset password</h1>
            <p className="mt-1 text-sm text-muted-foreground">
              Enter your email and we&apos;ll send a reset link.
            </p>

            {resetSent ? (
              <>
                <div className="mt-4 rounded-md bg-green-50 px-3 py-2 text-sm text-green-700">
                  Reset link sent! Check your inbox.
                </div>
                <button
                  onClick={() => switchMode("signin")}
                  className="mt-4 w-full rounded-md bg-black px-3 py-2 text-sm font-medium text-white hover:bg-black/90"
                >
                  Back to Sign In
                </button>
              </>
            ) : (
              <form onSubmit={handleSubmit} className="mt-4 space-y-3">
                <div className="space-y-1">
                  <label className="text-sm font-medium">Email</label>
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="w-full rounded-md border px-3 py-2 text-sm"
                    placeholder="you@example.com"
                  />
                </div>

                {(localError || error) && (
                  <div className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
                    {localError || error}
                  </div>
                )}

                <button
                  type="submit"
                  disabled={loading}
                  className="w-full rounded-md bg-black px-3 py-2 text-sm font-medium text-white hover:bg-black/90 disabled:opacity-50"
                >
                  {loading ? "Sending..." : "Send reset link"}
                </button>

                <div className="text-sm text-muted-foreground">
                  <button type="button" onClick={() => switchMode("signin")} className="text-foreground underline">
                    Back to Sign In
                  </button>
                </div>
              </form>
            )}
          </>

        /* ── Sign in / Sign up screen ── */
        ) : (
          <>
            <h1 className="text-xl font-semibold">{mode === "signin" ? "Sign in" : "Create account"}</h1>
            <p className="mt-1 text-sm text-muted-foreground">
              {mode === "signin" ? "Welcome back." : "Create an account to get started."}
            </p>

            <form onSubmit={handleSubmit} className="mt-4 space-y-3">
              <div className="space-y-1">
                <label className="text-sm font-medium">Email</label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full rounded-md border px-3 py-2 text-sm"
                  placeholder="you@example.com"
                />
              </div>
              <div className="space-y-1">
                <label className="text-sm font-medium">Password</label>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full rounded-md border px-3 py-2 text-sm"
                  placeholder="••••••••"
                />
                {mode === "signup" && (
                  <p className="text-xs text-muted-foreground">Minimum 8 characters</p>
                )}
              </div>
              {mode === "signup" && (
                <div className="space-y-1">
                  <label className="text-sm font-medium">Confirm Password</label>
                  <input
                    type="password"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    className="w-full rounded-md border px-3 py-2 text-sm"
                    placeholder="••••••••"
                  />
                </div>
              )}

              {(localError || error) && (
                <div className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
                  {localError || error}
                </div>
              )}

              <button
                type="submit"
                disabled={loading}
                className="w-full rounded-md bg-black px-3 py-2 text-sm font-medium text-white hover:bg-black/90 disabled:opacity-50"
              >
                {loading ? "Please wait..." : mode === "signin" ? "Sign in" : "Sign up"}
              </button>
            </form>

            <div className="mt-4 flex items-center justify-between text-sm text-muted-foreground">
              <span>
                {mode === "signin" ? "New here?" : "Already have an account?"}{" "}
                <button
                  type="button"
                  onClick={() => switchMode(mode === "signin" ? "signup" : "signin")}
                  className="text-foreground underline"
                >
                  {mode === "signin" ? "Create one" : "Sign in"}
                </button>
              </span>
              {mode === "signin" && (
                <button
                  type="button"
                  onClick={() => switchMode("forgot")}
                  className="text-foreground underline"
                >
                  Forgot password?
                </button>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
