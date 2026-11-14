/** Illustrated interviewer avatar: lip-sync from an audio level bus, blinks, nods and thinking poses. */
import React, { useEffect, useRef } from "react";

/** A tiny pub/sub so 60fps audio levels update the SVG without React re-renders. */
export function createLevelBus() {
  const listeners = new Set();
  return {
    emit: (value) => listeners.forEach((fn) => fn(value)),
    subscribe: (fn) => { listeners.add(fn); return () => listeners.delete(fn); },
  };
}

const HAIR_BACK = {
  long: "M116 178 C106 92 158 66 200 66 C246 66 296 94 286 182 L296 318 C262 334 138 334 104 318 Z",
  bob: "M118 182 C110 94 160 70 200 70 C244 70 292 94 282 182 L288 252 C262 266 138 266 112 252 Z",
  wavy: "M120 182 C108 96 158 70 200 70 C246 70 294 98 282 182 C292 214 286 240 270 252 C250 262 150 262 130 252 C114 240 108 214 120 182 Z",
  short: "",
};
const HAIR_FRONT = {
  short: "M124 168 C118 104 158 76 202 76 C248 76 284 104 276 168 C268 138 248 116 214 112 C196 122 160 120 140 136 C132 146 127 156 124 168 Z",
  bob: "M122 178 C116 100 160 72 202 72 C250 72 286 102 278 180 C266 140 240 118 214 110 C194 132 156 144 122 178 Z",
  long: "M120 182 C114 100 158 70 202 70 C250 70 288 102 280 184 C268 142 244 116 212 106 C190 132 152 146 120 182 Z",
  wavy: "M122 176 C112 104 160 72 204 72 C254 72 288 106 278 176 C270 154 258 140 244 132 C236 142 222 140 214 128 C204 140 186 142 176 130 C164 146 140 152 122 176 Z",
};

export default function Avatar({ persona, state = "idle", bus, size = "100%", label }) {
  const look = persona?.look || {};
  const mouthRef = useRef(null);
  const innerRef = useRef(null);
  const teethRef = useRef(null);
  const headRef = useRef(null);
  const smoothed = useRef(0);

  useEffect(() => {
    if (!bus) return undefined;
    return bus.subscribe((level) => {
      const v = (smoothed.current = smoothed.current * 0.55 + level * 0.45);
      const open = Math.min(1, v);
      if (innerRef.current) {
        innerRef.current.setAttribute("ry", (1.2 + open * 11).toFixed(2));
        innerRef.current.setAttribute("rx", (13 + open * 3).toFixed(2));
      }
      if (teethRef.current) teethRef.current.setAttribute("opacity", open > 0.25 ? "0.95" : "0");
      if (mouthRef.current) mouthRef.current.setAttribute("opacity", open > 0.04 ? "1" : "0");
      if (headRef.current) headRef.current.style.transform = `rotate(${(open * 1.6 - 0.4).toFixed(2)}deg) translateY(${(-open * 1.5).toFixed(2)}px)`;
    });
  }, [bus]);

  const skin = look.skin || "#E8B990";
  const shade = look.skin_shade || "#C99570";
  const hair = look.hair || "#2A1A14";
  const style = look.hair_style || "short";
  const eyes = look.eyes || "#2B2422";
  return (
    <svg
      className={`avatar avatar--${state}`}
      viewBox="0 0 400 400"
      width={size}
      height={size}
      role="img"
      aria-label={label || `${persona?.name || "Interviewer"}, ${state}`}
    >
      <defs>
        <radialGradient id={`glow-${persona?.key}`} cx="50%" cy="38%" r="70%">
          <stop offset="0%" stopColor={look.accent || "#9aa0e6"} stopOpacity="0.55" />
          <stop offset="100%" stopColor={look.accent || "#9aa0e6"} stopOpacity="0" />
        </radialGradient>
        <linearGradient id={`top-${persona?.key}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={look.top || "#3B4A6B"} />
          <stop offset="100%" stopColor={look.top || "#3B4A6B"} stopOpacity="0.82" />
        </linearGradient>
      </defs>
      <circle cx="200" cy="190" r="190" fill={`url(#glow-${persona?.key})`} />
      <g className="avatar-body">
        <path d="M54 400 C64 320 126 292 200 292 C274 292 336 320 346 400 Z" fill={`url(#top-${persona?.key})`} />
        <path d="M168 292 L200 330 L232 292" fill="none" stroke={look.accent || "#9aa0e6"} strokeWidth="5" strokeLinecap="round" opacity="0.7" />
        <rect x="176" y="236" width="48" height="66" rx="22" fill={shade} />
      </g>
      <g className="avatar-head" ref={headRef}>
        {HAIR_BACK[style] && <path d={HAIR_BACK[style]} fill={hair} />}
        <ellipse cx="128" cy="196" rx="12" ry="18" fill={shade} />
        <ellipse cx="272" cy="196" rx="12" ry="18" fill={shade} />
        <path d="M128 168 C128 110 160 90 200 90 C240 90 272 110 272 168 C272 228 246 270 200 272 C154 270 128 228 128 168 Z" fill={skin} />
        <ellipse cx="160" cy="214" rx="15" ry="9" fill="#e07a6a" opacity="0.16" />
        <ellipse cx="240" cy="214" rx="15" ry="9" fill="#e07a6a" opacity="0.16" />
        <path d={HAIR_FRONT[style]} fill={hair} />
        <g className="avatar-brows" stroke={hair} strokeWidth="5" strokeLinecap="round" fill="none">
          <path d="M156 152 Q172 144 188 150" />
          <path d="M212 150 Q228 144 244 152" />
        </g>
        <g className="avatar-eyes">
          <g className="avatar-eye">
            <ellipse cx="172" cy="174" rx="11" ry="8" fill="#fff" />
            <circle className="avatar-iris" cx="172" cy="174" r="6" fill={eyes} />
            <circle cx="174" cy="172" r="1.8" fill="#fff" />
          </g>
          <g className="avatar-eye">
            <ellipse cx="228" cy="174" rx="11" ry="8" fill="#fff" />
            <circle className="avatar-iris" cx="228" cy="174" r="6" fill={eyes} />
            <circle cx="230" cy="172" r="1.8" fill="#fff" />
          </g>
        </g>
        {look.glasses && (
          <g stroke="#1d1d24" strokeWidth="3.5" fill="none" opacity="0.9">
            <rect x="152" y="160" width="40" height="30" rx="10" />
            <rect x="208" y="160" width="40" height="30" rx="10" />
            <path d="M192 172 Q200 166 208 172" />
          </g>
        )}
        <path d="M200 182 C195 200 193 207 203 209" fill="none" stroke={shade} strokeWidth="3.5" strokeLinecap="round" />
        <path className="avatar-smile" d="M182 232 Q200 242 218 232" fill="none" stroke="#9c4a45" strokeWidth="4" strokeLinecap="round" />
        <g ref={mouthRef} opacity="0">
          <ellipse ref={innerRef} cx="200" cy="236" rx="13" ry="1" fill="#5a2228" />
          <rect ref={teethRef} x="190" y="227" width="20" height="5" rx="2" fill="#fff" opacity="0" />
        </g>
      </g>
      {state === "thinking" && (
        <g className="avatar-thinking" fill={look.accent || "#9aa0e6"}>
          <circle cx="306" cy="96" r="7" />
          <circle cx="328" cy="78" r="9" />
          <circle cx="354" cy="56" r="11" />
        </g>
      )}
    </svg>
  );
}
