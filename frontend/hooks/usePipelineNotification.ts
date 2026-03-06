"use client";

import { useEffect, useRef } from "react";

/**
 * Requests browser notification permission when tailoring starts, then fires a
 * notification when the pipeline completes and the user is on a different tab.
 *
 * @param applicationId  ID used to build the review URL for the notification click handler
 * @param onComplete     Call this with applicationId when the pipeline is done and
 *                       we should navigate — pass null if navigation is handled elsewhere
 */
export function usePipelineNotification(
  applicationId: string | null,
  isTailoring: boolean,
): void {
  const permissionRequested = useRef(false);
  const wasRunning = useRef(false);

  // Request permission as soon as tailoring starts (must be in response to user action
  // context — calling it early maximises chances it was triggered by a button click).
  useEffect(() => {
    if (!isTailoring) return;
    wasRunning.current = true;
    if (permissionRequested.current) return;
    if (typeof Notification === "undefined") return;
    if (Notification.permission === "default") {
      Notification.requestPermission().catch(() => {});
    }
    permissionRequested.current = true;
  }, [isTailoring]);

  // Fire notification when tailoring transitions false (complete) and tab is hidden.
  useEffect(() => {
    if (!wasRunning.current) return;
    if (isTailoring) return;  // still running
    wasRunning.current = false;

    if (typeof Notification === "undefined") return;
    if (Notification.permission !== "granted") return;
    if (!document.hidden) return;  // user is already looking at the tab
    if (!applicationId) return;

    const notification = new Notification("Your CV is ready to review!", {
      body: "Tailoring complete — click to open your review page.",
      icon: "/favicon.ico",
    });

    notification.onclick = () => {
      window.focus();
      window.location.href = `/review/${applicationId}`;
    };
  }, [isTailoring, applicationId]);
}
