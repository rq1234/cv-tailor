"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { applicationSchema, type Application } from "@/lib/schemas";
import { z } from "zod";

const STATUS_LABEL: Record<string, { label: string; className: string }> = {
  draft:      { label: "Draft",            className: "bg-gray-100 text-gray-600" },
  tailoring:  { label: "Processing...",    className: "bg-yellow-50 text-yellow-700" },
  review:     { label: "Ready to Review",  className: "bg-blue-50 text-blue-700" },
  complete:   { label: "Complete",         className: "bg-green-50 text-green-700" },
};

export default function ApplicationsPage() {
  const [applications, setApplications] = useState<Application[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchApplications = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.get<Application[]>("/api/applications");
      setApplications(z.array(applicationSchema).parse(data));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load applications");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchApplications();
  }, [fetchApplications]);

  if (loading) {
    return (
      <div className="flex justify-center py-20">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 p-6">
        <p className="text-sm text-red-700">{error}</p>
        <button onClick={fetchApplications} className="mt-3 rounded-md border px-3 py-1.5 text-sm hover:bg-muted">
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Applications</h1>
        <Link
          href="/apply"
          className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
        >
          New Application
        </Link>
      </div>

      {applications.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-lg border border-dashed p-12 text-center">
          <p className="text-lg text-muted-foreground">No applications yet</p>
          <p className="mt-1 text-sm text-muted-foreground">
            Start a new application to tailor your CV for a specific role.
          </p>
          <Link
            href="/apply"
            className="mt-4 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
          >
            New Application
          </Link>
        </div>
      ) : (
        <div className="overflow-hidden rounded-lg border">
          <table className="w-full text-sm">
            <thead className="border-b bg-muted/50">
              <tr>
                <th className="px-4 py-3 text-left font-medium">Company</th>
                <th className="px-4 py-3 text-left font-medium">Role</th>
                <th className="px-4 py-3 text-left font-medium">Status</th>
                <th className="px-4 py-3 text-left font-medium">Date</th>
                <th className="px-4 py-3 text-right font-medium"></th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {applications.map((app) => {
                const status = STATUS_LABEL[app.status] ?? { label: app.status, className: "bg-gray-100 text-gray-600" };
                const date = new Date(app.created_at).toLocaleDateString("en-GB", {
                  day: "numeric", month: "short", year: "numeric",
                });
                return (
                  <tr key={app.id} className="hover:bg-muted/30 transition-colors">
                    <td className="px-4 py-3 font-medium">{app.company_name}</td>
                    <td className="px-4 py-3 text-muted-foreground">{app.role_title || "—"}</td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${status.className}`}>
                        {status.label}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">{date}</td>
                    <td className="px-4 py-3 text-right">
                      {(app.status === "review" || app.status === "complete") && (
                        <Link
                          href={`/review/${app.id}`}
                          className="rounded-md border px-3 py-1 text-xs font-medium hover:bg-muted"
                        >
                          Review
                        </Link>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
