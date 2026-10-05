/** SVG practice plant whose leaves reflect completed interviews. */
import React from "react";

const MAX_LEAVES = 12;

/** Draw one alternating branch and leaf; the newest leaf may unfurl. */
function Leaf({ index, celebrate }) {
  const direction = index % 2 === 0 ? -1 : 1;
  const y = 106 - index * 6;
  const length = 24 + Math.floor(index / 2) * 3;
  const baseX = 90 + direction * 9;
  const tipX = 90 + direction * (length + 15);
  const tipY = y - 18;
  const leafPath = [
    `M ${baseX} ${y - 4}`,
    `Q ${baseX + direction * 10} ${y - 22} ${tipX} ${tipY - 7}`,
    `Q ${tipX - direction * 3} ${tipY + 8} ${baseX} ${y - 4}`,
    "Z",
  ].join(" ");

  return (
    <g
      className={`practice-plant-leaf${celebrate ? " is-new" : ""}`}
      data-testid={celebrate ? "leaf-new" : "leaf-grown"}
      style={{ "--branch-y": `${y}px` }}
    >
      <path d={`M 90 ${y} Q ${90 + direction * 4} ${y - 5} ${baseX} ${y - 4}`} className="practice-plant-branch" />
      <path d={leafPath} className={index % 4 < 2 ? "practice-plant-leaf-fill" : "practice-plant-leaf-fill is-light"} />
      <path d={`M ${baseX} ${y - 4} Q ${90 + direction * (length - 1)} ${tipY - 3} ${tipX} ${tipY - 7}`} className="practice-plant-vein" />
    </g>
  );
}

/** Keep a starter sprout visible and cap added leaves at twelve. */
export default function PracticePlant({ completed = 0, celebrate = false }) {
  const count = Math.max(0, Number(completed) || 0);
  const visibleLeaves = Math.min(count, MAX_LEAVES);
  const top = Math.min(86, 113 - visibleLeaves * 6.5);

  return (
    <svg
      className={`practice-plant${celebrate ? " is-celebrating" : ""}`}
      viewBox="25 10 130 145"
      role="img"
      aria-label={`A practice plant grown by ${count} completed interviews`}
    >
      <ellipse cx="90" cy="151" rx="47" ry="4" className="practice-plant-shadow" />
      <path d={`M 90 118 C 88 100 93 ${top + 16} 90 ${top}`} className="practice-plant-stem" />
      <path d="M 90 89 C 80 77 68 76 64 80 C 66 91 78 96 90 89 Z" className="practice-plant-starter-leaf" data-testid="leaf-starter" />
      <path d="M 90 89 C 100 76 112 75 117 79 C 115 91 103 95 90 89 Z" className="practice-plant-starter-leaf" data-testid="leaf-starter" />
      {Array.from({ length: visibleLeaves }, (_, index) => (
        <Leaf key={index} index={index} celebrate={celebrate && index === visibleLeaves - 1} />
      ))}
      <path d="M 47 119 H 133 L 126 145 Q 125 150 118 150 H 62 Q 55 150 54 145 Z" className="practice-plant-pot" />
      <path d="M 45 117 Q 45 114 49 114 H 131 Q 135 114 135 117 V 121 H 45 Z" className="practice-plant-pot-rim" />
      <circle cx="79" cy="133" r="1.6" className="practice-plant-face" />
      <circle cx="101" cy="133" r="1.6" className="practice-plant-face" />
      <path d="M 85 139 Q 90 143 95 139" className="practice-plant-smile" />
    </svg>
  );
}
