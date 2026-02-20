"use client";

import { useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/store/authStore";
import { api } from "@/lib/api";

const steps = [
  {
    number: "1",
    title: "Upload your CV",
    description: "Drop in your existing PDF. We extract every role, project, skill, and degree into a searchable library.",
  },
  {
    number: "2",
    title: "Paste the job description",
    description: "Enter the company, role, and JD. Our AI picks the most relevant experience and rewrites bullets to match.",
  },
  {
    number: "3",
    title: "Review & export to Overleaf",
    description: "Accept, reject, or edit each suggestion. One click sends the final LaTeX straight to Overleaf.",
  },
];

export default function LandingPage() {
  const router = useRouter();
  const { user, initializing } = useAuthStore();

  useEffect(() => {
    if (initializing || !user) return;
    // Authenticated users get smart-redirected
    api
      .get<{ work_experiences: unknown[]; education: unknown[]; projects: unknown[]; activities: unknown[]; skills: unknown[] }>("/api/cv/pool")
      .then((pool) => {
        const hasContent =
          pool.work_experiences.length > 0 ||
          pool.education.length > 0 ||
          pool.projects.length > 0 ||
          pool.activities.length > 0 ||
          pool.skills.length > 0;
        router.replace(hasContent ? "/library" : "/upload");
      })
      .catch(() => router.replace("/library"));
  }, [user, initializing, router]);

  // Show nothing while checking auth (AuthProvider handles the loading screen)
  if (initializing || user) return null;

  return (
    <div className="mx-auto max-w-4xl px-4 py-20 text-center">
      {/* Hero */}
      <h1 className="text-4xl font-bold tracking-tight sm:text-5xl">
        Tailor your CV to every job — in minutes
      </h1>
      <p className="mx-auto mt-4 max-w-xl text-lg text-muted-foreground">
        CV Tailor uses AI to rewrite your experience bullets for each application, then exports a polished LaTeX CV straight to Overleaf.
      </p>
      <div className="mt-8 flex justify-center gap-3">
        <Link
          href="/login?mode=signup"
          className="rounded-md bg-primary px-6 py-3 text-sm font-semibold text-primary-foreground hover:bg-primary/90"
        >
          Get started free
        </Link>
        <Link
          href="/login"
          className="rounded-md border px-6 py-3 text-sm font-semibold hover:bg-muted"
        >
          Sign in
        </Link>
      </div>

      {/* Steps */}
      <div className="mt-20 grid gap-8 sm:grid-cols-3">
        {steps.map((step) => (
          <div key={step.number} className="rounded-lg border bg-white p-6 text-left shadow-sm">
            <div className="mb-3 flex h-8 w-8 items-center justify-center rounded-full bg-primary text-sm font-bold text-primary-foreground">
              {step.number}
            </div>
            <h3 className="font-semibold">{step.title}</h3>
            <p className="mt-1 text-sm text-muted-foreground">{step.description}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
