"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuthStore } from "@/store/authStore";
import { api } from "@/lib/api";

const benefits = [
  "AI rewrites your existing bullets — not generic templates",
  "Review and accept every change before it goes in your CV",
  "Exports polished LaTeX straight to Overleaf in one click",
];

export default function LoginPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const {
    signIn,
    signUp,
    resetPassword,
    resendConfirmation,
    loading,
    error,
    signupEmail,
    clearSignupEmail,
    user,
    initializing,
  } = useAuthStore();

  const redirectAfterAuth = useCallback(async () => {
    try {
      const pool = await api.get<{
        work_experiences: unknown[];
        education: unknown[];
        projects: unknown[];
        activities: unknown[];
        skills: unknown[];
      }>("/api/cv/pool");
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
      if (success) await redirectAfterAuth();
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
    <div className="flex min-h-[calc(100vh-8rem)] overflow-hidden rounded-xl border shadow-sm">
      {/* ── Left: brand panel ── */}
      <div className="hidden lg:flex lg:w-[42%] flex-col justify-between bg-zinc-900 p-10 text-white">
        <div>
          <div className="text-xl font-bold">CV Tailor</div>
          <p className="mt-0.5 text-xs text-zinc-400">AI-powered CV tailoring</p>
        </div>

        <div className="space-y-6">
          <h2 className="text-2xl font-bold leading-snug">
            The fastest way to tailor your CV for every application.
          </h2>
          <ul className="space-y-3 text-sm text-zinc-300">
            {benefits.map((b) => (
              <li key={b} className="flex items-start gap-2">
                <span className="mt-0.5 flex-shrink-0 text-green-400 font-bold">✓</span>
                <span>{b}</span>
              </li>
            ))}
          </ul>
        </div>

        <p className="text-xs text-zinc-600">© {new Date().getFullYear()} CV Tailor</p>
      </div>

      {/* ── Right: form panel ── */}
      <div className="flex flex-1 items-center justify-center bg-white p-8">
        <div className="w-full max-w-sm">

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
                className="mt-2 w-full rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
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
                    className="mt-4 w-full rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
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
                      className="w-full rounded-md border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
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
                    className="w-full rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
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
              <h1 className="text-xl font-semibold">
                {mode === "signin" ? "Welcome back" : "Create your account"}
              </h1>
              <p className="mt-1 text-sm text-muted-foreground">
                {mode === "signin"
                  ? "Sign in to continue to CV Tailor."
                  : "Start tailoring your CV to every job."}
              </p>

              <form onSubmit={handleSubmit} className="mt-6 space-y-4">
                <div className="space-y-1">
                  <label className="text-sm font-medium">Email</label>
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="w-full rounded-md border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                    placeholder="you@example.com"
                    autoComplete="email"
                  />
                </div>

                <div className="space-y-1">
                  <label className="text-sm font-medium">Password</label>
                  <input
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="w-full rounded-md border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                    placeholder="••••••••"
                    autoComplete={mode === "signin" ? "current-password" : "new-password"}
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
                      className="w-full rounded-md border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                      placeholder="••••••••"
                      autoComplete="new-password"
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
                  className="w-full rounded-md bg-primary px-3 py-2 text-sm font-semibold text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-colors"
                >
                  {loading
                    ? "Please wait..."
                    : mode === "signin"
                    ? "Sign in"
                    : "Get started free"}
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
    </div>
  );
}
