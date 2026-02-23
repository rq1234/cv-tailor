"use client";

import { useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/store/authStore";
import { api } from "@/lib/api";

function ProductMockup() {
  return (
    <div className="rounded-xl border bg-white shadow-2xl overflow-hidden">
      {/* Fake browser chrome */}
      <div className="border-b bg-gray-50 px-4 py-2.5 flex items-center gap-2">
        <div className="h-2.5 w-2.5 rounded-full bg-red-400" />
        <div className="h-2.5 w-2.5 rounded-full bg-yellow-400" />
        <div className="h-2.5 w-2.5 rounded-full bg-green-400" />
        <span className="ml-2 text-xs text-gray-400 font-medium">Review — Google · Software Engineer</span>
      </div>

      {/* App content */}
      <div className="p-4 space-y-3 bg-gray-50/50">
        <div className="text-[10px] font-semibold uppercase tracking-widest text-gray-400">
          Work Experience · 2 suggestions
        </div>

        {/* Bullet 1 — accepted */}
        <div className="rounded-lg border border-green-200 bg-green-50 p-3">
          <div className="flex items-start gap-2">
            <span className="mt-0.5 flex-shrink-0 flex h-4 w-4 items-center justify-center rounded-full bg-green-500 text-white text-[9px] font-bold">✓</span>
            <p className="text-xs text-gray-700 leading-relaxed">
              Reduced API latency by <strong>40%</strong> by introducing Redis caching for
              frequently-queried datasets, improving p99 response times from 800 ms to 480 ms.
            </p>
          </div>
          <div className="mt-2">
            <span className="rounded-full bg-green-600 px-2 py-0.5 text-[10px] text-white font-medium">
              Accepted
            </span>
          </div>
        </div>

        {/* Bullet 2 — pending */}
        <div className="rounded-lg border bg-white p-3 shadow-sm">
          <div className="flex items-start gap-2">
            <span className="mt-0.5 flex-shrink-0 flex h-4 w-4 items-center justify-center rounded-full bg-gray-200 text-gray-500 text-[9px] font-bold">2</span>
            <p className="text-xs text-gray-700 leading-relaxed">
              Led a cross-functional team of 5 engineers to ship a{" "}
              <strong>real-time data pipeline</strong> processing 50 k events/sec, cutting
              batch processing time by 65%.
            </p>
          </div>
          <div className="mt-2 flex gap-1.5">
            <button className="rounded-full bg-black px-2.5 py-0.5 text-[10px] text-white font-medium">Accept</button>
            <button className="rounded-full border px-2.5 py-0.5 text-[10px] text-gray-600 font-medium">Edit</button>
            <button className="rounded-full border px-2.5 py-0.5 text-[10px] text-gray-600 font-medium">Skip</button>
          </div>
        </div>

        {/* Export bar */}
        <div className="rounded-lg border bg-white p-3 shadow-sm flex items-center justify-between">
          <span className="text-xs text-gray-500">2 of 6 reviewed</span>
          <button className="rounded-md bg-black px-3 py-1.5 text-[10px] font-semibold text-white">
            Export to Overleaf →
          </button>
        </div>
      </div>
    </div>
  );
}

const steps = [
  {
    number: "1",
    title: "Upload your CV",
    description:
      "Drop in your existing PDF. We extract every role, project, skill, and degree into a searchable library.",
  },
  {
    number: "2",
    title: "Paste the job description",
    description:
      "Enter the company, role, and JD. Our AI picks the most relevant experience and rewrites bullets to match.",
  },
  {
    number: "3",
    title: "Review & export to Overleaf",
    description:
      "Accept, reject, or edit each suggestion. One click sends the final LaTeX straight to Overleaf.",
  },
];

export default function LandingPage() {
  const router = useRouter();
  const { user, initializing } = useAuthStore();

  useEffect(() => {
    if (initializing || !user) return;
    api
      .get<{
        work_experiences: unknown[];
        education: unknown[];
        projects: unknown[];
        activities: unknown[];
        skills: unknown[];
      }>("/api/cv/pool")
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

  if (initializing || user) return null;

  return (
    <div className="py-10">
      {/* ── Hero — split layout ── */}
      <div className="grid items-center gap-12 lg:grid-cols-2">
        {/* Left: copy */}
        <div>
          <div className="mb-4 inline-flex items-center rounded-full border bg-muted px-3 py-1 text-xs text-muted-foreground">
            AI-powered · Free to get started
          </div>
          <h1 className="text-4xl font-bold tracking-tight sm:text-5xl leading-tight">
            Land more interviews.{" "}
            <span className="text-muted-foreground">
              Stop rewriting your CV from scratch.
            </span>
          </h1>
          <p className="mt-5 text-lg text-muted-foreground leading-relaxed">
            Paste a job description. CV Tailor rewrites your existing bullet
            points to match — then exports a polished LaTeX CV straight to
            Overleaf in one click.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link
              href="/login?mode=signup"
              className="rounded-md bg-primary px-6 py-3 text-sm font-semibold text-primary-foreground hover:bg-primary/90 transition-colors"
            >
              Get started free
            </Link>
            <Link
              href="/login"
              className="rounded-md border px-6 py-3 text-sm font-semibold hover:bg-muted transition-colors"
            >
              Sign in
            </Link>
          </div>
          <p className="mt-3 text-xs text-muted-foreground">
            No credit card required.
          </p>
          <p className="mt-2 text-sm font-medium text-primary">
            CVTailorAlpha is coming soon.
          </p>
        </div>

        {/* Right: product mockup */}
        <div className="lg:pl-6">
          <ProductMockup />
        </div>
      </div>

      {/* ── How it works ── */}
      <div className="mt-28">
        <div className="text-center mb-10">
          <h2 className="text-2xl font-bold">How it works</h2>
          <p className="mt-2 text-sm text-muted-foreground">Three steps from PDF to a tailored CV.</p>
        </div>
        <div className="grid gap-6 sm:grid-cols-3">
          {steps.map((step) => (
            <div
              key={step.number}
              className="rounded-lg border bg-white p-6 shadow-sm"
            >
              <div className="mb-3 flex h-8 w-8 items-center justify-center rounded-full bg-primary text-sm font-bold text-primary-foreground">
                {step.number}
              </div>
              <h3 className="font-semibold">{step.title}</h3>
              <p className="mt-1 text-sm text-muted-foreground">
                {step.description}
              </p>
            </div>
          ))}
        </div>
      </div>

      {/* ── Bottom CTA ── */}
      <div className="mt-20 rounded-xl border bg-zinc-900 px-8 py-12 text-center text-white">
        <h2 className="text-2xl font-bold">Ready to tailor your first application?</h2>
        <p className="mt-2 text-sm text-zinc-400">
          Upload your CV once. Tailor it to every job in minutes.
        </p>
        <Link
          href="/login?mode=signup"
          className="mt-6 inline-block rounded-md bg-white px-6 py-3 text-sm font-semibold text-zinc-900 hover:bg-zinc-100 transition-colors"
        >
          Get started free
        </Link>
      </div>
    </div>
  );
}
