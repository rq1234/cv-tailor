"use client";

import {
  type BulletState,
  type ExperienceDiff,
  type TailorResult,
  getDiffMeta,
} from "./types";

// Letter paper at 96 DPI: 8.5" × 11" = 816 × 1056px
// Margins: 0.5" = 48px each side → text area: 720 × 960px
// Page break line sits at padding-top (48) + text-height (960) = 1008px from page top

const PAGE_W = 816;
const PAGE_H = 1056;
const MARGIN = 48; // 0.5in at 96dpi
const TEXT_H = 960; // 10in text area

const pageStyle: React.CSSProperties = {
  width: PAGE_W,
  minHeight: PAGE_H,
  backgroundColor: "#fff",
  position: "relative",
  fontFamily: '"CMU Serif", "Computer Modern", Georgia, "Times New Roman", serif',
  fontSize: "11pt",
  lineHeight: 1.15,
  color: "#000",
};

const contentStyle: React.CSSProperties = {
  padding: `${MARGIN}px`,
};

// Section heading: small-caps, large, with bottom rule — mirrors \titleformat{\section}
function SectionHeading({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ marginTop: 10, marginBottom: 3 }}>
      <div
        style={{
          fontVariant: "small-caps",
          fontSize: "13pt",
          fontWeight: 400,
          letterSpacing: "0.02em",
          lineHeight: 1.1,
          marginBottom: 2,
        }}
      >
        {children}
      </div>
      <div style={{ borderBottom: "1px solid #000", marginBottom: 4 }} />
    </div>
  );
}

// Subheading row: bold name + date on same line — mirrors \resumeSubheading
function SubHeading({
  title,
  subtitle,
  dateRange,
  isProject = false,
}: {
  title: string;
  subtitle?: string | null;
  dateRange?: string | null;
  isProject?: boolean;
}) {
  return (
    <div style={{ marginTop: 4, marginBottom: 1 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
        <span style={{ fontWeight: "bold", fontSize: "11pt" }}>{title}</span>
        {dateRange && (
          <span style={{ fontStyle: "italic", fontSize: "10pt", flexShrink: 0, marginLeft: 8 }}>
            {dateRange}
          </span>
        )}
      </div>
      {subtitle && !isProject && (
        <div style={{ fontStyle: "italic", fontSize: "10pt", color: "#222" }}>{subtitle}</div>
      )}
    </div>
  );
}

// Bullet list — mirrors \resumeItemListStart / \resumeItem
function BulletList({ bullets, decisions, originalBullets }: {
  bullets: Array<{ text: string; has_placeholder?: boolean } | string>;
  decisions?: Record<number, BulletState>;
  originalBullets?: string[];
}) {
  return (
    <ul style={{ margin: "2px 0 4px 18px", padding: 0, listStyleType: "disc" }}>
      {bullets.map((b, idx) => {
        const raw = typeof b === "string" ? b : b.text;
        const hasPlaceholder = typeof b === "object" && b.has_placeholder;
        const bulletState = decisions?.[idx];
        const isRejected = bulletState?.decision === "reject";
        const displayText = bulletState?.editedText
          ? bulletState.editedText
          : isRejected
          ? (originalBullets?.[idx] ?? raw)
          : raw;

        let color = "#000";
        if (isRejected) color = "#555";
        else if (bulletState?.decision === "accept" && displayText !== originalBullets?.[idx]) color = "#166534";
        else if (hasPlaceholder) color = "#92400e";

        return (
          <li
            key={idx}
            style={{
              fontSize: "10pt",
              lineHeight: 1.2,
              marginBottom: 1,
              color,
            }}
          >
            {displayText}
          </li>
        );
      })}
    </ul>
  );
}

interface CvPagePreviewProps {
  result: TailorResult;
  experienceDiffs: [string, ExperienceDiff][];
  projectDiffs: [string, ExperienceDiff][];
  activityDiffs: [string, ExperienceDiff][];
  decisions: Record<string, Record<number, BulletState>>;
  manualEdits?: Record<string, string>;
}

export default function CvPagePreview({
  result,
  experienceDiffs,
  projectDiffs,
  activityDiffs,
  decisions,
  manualEdits = {},
}: CvPagePreviewProps) {
  const profile = result.profile;

  const sections = [
    { label: "Experience", entries: experienceDiffs },
    { label: "Projects", entries: projectDiffs },
    { label: "Leadership & Activities", entries: activityDiffs },
  ].filter((s) => s.entries.length > 0);

  return (
    // Outer: PDF-viewer-style gray background, horizontally scrollable
    <div
      style={{
        backgroundColor: "#e5e7eb",
        padding: "32px 16px",
        overflowX: "auto",
        minHeight: 400,
      }}
    >
      {/* Page hint */}
      <p style={{ textAlign: "center", fontSize: "11px", color: "#6b7280", marginBottom: 12, fontFamily: "sans-serif" }}>
        Letter paper · 8.5″ × 11″ · 0.5″ margins · Computer Modern 11pt
      </p>

      {/* Letter page */}
      <div style={{ ...pageStyle, margin: "0 auto", boxShadow: "0 4px 24px rgba(0,0,0,0.18)" }}>

        {/* Page-break indicator — sits at exactly 10" text area from top of page */}
        <div
          style={{
            position: "absolute",
            top: MARGIN + TEXT_H,
            left: 0,
            right: 0,
            zIndex: 10,
            pointerEvents: "none",
          }}
        >
          <div style={{ borderTop: "2px dashed #ef4444" }} />
          <div style={{
            textAlign: "center",
            fontSize: "10px",
            fontFamily: "sans-serif",
            color: "#ef4444",
            background: "#fff",
            display: "inline-block",
            padding: "1px 8px",
            marginLeft: "50%",
            transform: "translateX(-50%)",
          }}>
            — Page 2 begins here —
          </div>
        </div>

        <div style={contentStyle}>
          {/* ── Header: name + contact ── */}
          {profile && (
            <div style={{ textAlign: "center", marginBottom: 8 }}>
              {profile.full_name && (
                <div style={{ fontSize: "20pt", fontWeight: "bold", fontVariant: "small-caps", letterSpacing: "0.04em" }}>
                  {profile.full_name}
                </div>
              )}
              <div style={{ fontSize: "10pt", marginTop: 2, color: "#222" }}>
                {[profile.phone, profile.location, profile.email]
                  .filter(Boolean)
                  .join("  ·  ")}
              </div>
            </div>
          )}

          {/* ── Education ── */}
          {result.education_data?.length > 0 && (
            <div>
              <SectionHeading>Education</SectionHeading>
              {result.education_data.map((edu) => (
                <div key={edu.id} style={{ marginBottom: 4 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
                    <span style={{ fontWeight: "bold", fontSize: "11pt" }}>{edu.institution}</span>
                    {edu.date_end && (
                      <span style={{ fontStyle: "italic", fontSize: "10pt" }}>
                        {edu.date_start ? `${edu.date_start} – ` : ""}{edu.date_end}
                      </span>
                    )}
                  </div>
                  {edu.degree && (
                    <div style={{ fontStyle: "italic", fontSize: "10pt" }}>{edu.degree}</div>
                  )}
                  {edu.grade && (
                    <div style={{ fontSize: "10pt" }}>{edu.grade}</div>
                  )}
                  {edu.achievements?.length > 0 && (
                    <BulletList bullets={edu.achievements.map(String)} />
                  )}
                  {edu.modules?.length > 0 && (
                    <div style={{ fontSize: "10pt", marginTop: 2 }}>
                      <span style={{ fontWeight: "bold" }}>Coursework: </span>
                      {(manualEdits[`modules_${edu.id}`] || edu.modules.join(", "))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* ── Experience / Projects / Activities ── */}
          {sections.map((section) => (
            <div key={section.label}>
              <SectionHeading>{section.label}</SectionHeading>
              {section.entries.map(([id, diff]) => {
                const meta = getDiffMeta(id, diff, result);
                const entryDecisions = decisions[id] ?? {};
                return (
                  <div key={id} style={{ marginBottom: 4 }}>
                    <SubHeading
                      title={meta.title}
                      subtitle={meta.subtitle}
                      dateRange={meta.dateRange ?? null}
                      isProject={meta.isProject}
                    />
                    <BulletList
                      bullets={diff.suggested_bullets}
                      decisions={entryDecisions}
                      originalBullets={diff.original_bullets}
                    />
                  </div>
                );
              })}
            </div>
          ))}

          {/* ── Skills ── */}
          {result.skills_data && Object.keys(result.skills_data).length > 0 && (
            <div>
              <SectionHeading>Technical Skills</SectionHeading>
              <div style={{ fontSize: "10pt" }}>
                {Object.entries(result.skills_data).map(([category, skills]) => {
                  const key = `skills_${category}`;
                  const value = manualEdits[key] || (skills as string[]).join(", ");
                  return (
                    <div key={category} style={{ lineHeight: 1.3, marginBottom: 2 }}>
                      <span style={{ fontWeight: "bold" }}>{category}: </span>
                      <span>{value}</span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
