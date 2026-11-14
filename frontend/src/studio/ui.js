/** Small shared UI pieces. */
import React from "react";

export function Spinner({ label }) {
  return (
    <span className="spinner" role="status">
      <span className="spinner-dot" />
      {label && <span>{label}</span>}
    </span>
  );
}

export function ScoreRing({ score = 0, size = 112 }) {
  const pct = Math.max(0, Math.min(1, score / 5));
  const r = 44;
  const c = 2 * Math.PI * r;
  return (
    <svg className="score-ring" width={size} height={size} viewBox="0 0 100 100" aria-label={`Score ${score} out of 5`}>
      <circle cx="50" cy="50" r={r} className="score-ring-track" />
      <circle cx="50" cy="50" r={r} className="score-ring-fill" strokeDasharray={`${c * pct} ${c}`} transform="rotate(-90 50 50)" />
      <text x="50" y="54" textAnchor="middle" className="score-ring-text">{Number(score).toFixed(1)}</text>
      <text x="50" y="70" textAnchor="middle" className="score-ring-sub">of 5</text>
    </svg>
  );
}

export const READINESS = {
  ready: { label: "Interview-ready", tone: "good" },
  close: { label: "Almost there", tone: "warm" },
  developing: { label: "Keep building", tone: "cool" },
};

export const PROVENANCE = {
  official_guidance: { label: "Based on official guidance", tone: "good" },
  commonly_reported: { label: "Commonly reported", tone: "warm" },
  practice: { label: "Practice question", tone: "cool" },
  from_your_resume: { label: "From your resume", tone: "violet" },
};

export function Badge({ tone = "cool", children, title }) {
  return <span className={`badge badge--${tone}`} title={title}>{children}</span>;
}

export function formatDate(value) {
  if (!value) return "";
  const date = new Date(value);
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric", year: date.getFullYear() === new Date().getFullYear() ? undefined : "numeric" });
}

export function Empty({ title, children, action }) {
  return (
    <div className="empty">
      <h3>{title}</h3>
      <p>{children}</p>
      {action}
    </div>
  );
}
