"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/store/authStore";

export default function LoginPage() {
  const router = useRouter();
  const { signIn, signUp, loading, error, signupEmail, clearSignupEmail } = useAuthStore();
  const [mode, setMode] = useState<"signin" | "signup">("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [localError, setLocalError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLocalError(null);
    if (!email || !password) {
      setLocalError("Email and password are required.");
      return;
    }

    if (mode === "signup" && password !== confirmPassword) {
      setLocalError("Passwords do not match.");
      return;
    }

    if (mode === "signin") {
      await signIn(email, password);
    } else {
      await signUp(email, password);
    }

    const authError = error || localError;
    if (!authError) {
      router.replace("/library");
    }
  };

  return (
    <div className="mx-auto flex min-h-[80vh] max-w-md items-center">
      <div className="w-full rounded-lg border bg-white p-6 shadow-sm">
        {signupEmail ? (
          <>
            <h1 className="text-xl font-semibold">Check your email</h1>
            <p className="mt-1 text-sm text-muted-foreground">
              We sent a confirmation link to <strong>{signupEmail}</strong>
            </p>

            <div className="mt-4 rounded-md bg-blue-50 px-3 py-2 text-sm text-blue-700">
              Please click the link in your email to verify your account. Then you can sign in.
            </div>

            <button
              onClick={() => {
                clearSignupEmail();
                setMode("signin");
                setEmail("");
                setPassword("");
                setConfirmPassword("");
                setLocalError(null);
              }}
              className="mt-4 w-full rounded-md bg-black px-3 py-2 text-sm font-medium text-white hover:bg-black/90"
            >
              Back to Sign In
            </button>
          </>
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
            className="w-full rounded-md bg-black px-3 py-2 text-sm font-medium text-white hover:bg-black/90"
          >
            {loading ? "Please wait..." : mode === "signin" ? "Sign in" : "Sign up"}
          </button>
        </form>

        <div className="mt-4 text-sm text-muted-foreground">
          {mode === "signin" ? "New here?" : "Already have an account?"} {" "}
          <button
            type="button"
            onClick={() => {
              setMode(mode === "signin" ? "signup" : "signin");
              setPassword("");
              setConfirmPassword("");
              setLocalError(null);
            }}
            className="text-foreground underline"
          >
            {mode === "signin" ? "Create one" : "Sign in"}
          </button>
        </div>
          </>
        )}
      </div>
    </div>
  );
}
