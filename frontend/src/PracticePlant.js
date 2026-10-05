import React from "react";

const LEAVES = [
  { x: "15%", y: "12%", angle: -42 },
  { x: "72%", y: "12%", angle: 31 },
  { x: "3%", y: "43%", angle: -70 },
  { x: "82%", y: "43%", angle: 56 },
  { x: "25%", y: "49%", angle: -30 },
  { x: "74%", y: "52%", angle: 38 },
  { x: "30%", y: "26%", angle: -39 },
  { x: "60%", y: "31%", angle: 35 },
  { x: "8%", y: "32%", angle: -58 },
  { x: "77%", y: "29%", angle: 51 },
  { x: "20%", y: "56%", angle: -35 },
  { x: "69%", y: "58%", angle: 43 },
  { x: "20%", y: "5%", angle: -35 },
  { x: "67%", y: "5%", angle: 32 },
  { x: "1%", y: "52%", angle: -73 },
  { x: "85%", y: "52%", angle: 61 },
  { x: "35%", y: "44%", angle: -30 },
  { x: "61%", y: "47%", angle: 34 },
];

export default function PracticePlant({ completed = 0, celebrate = false }) {
  const visibleLeaves = Math.min(Math.max(completed, 0), LEAVES.length);
  return (
    <div className={`practice-plant${celebrate ? " is-celebrating" : ""}`} role="img" aria-label={`A practice plant grown by ${completed} completed interviews`}>
      <img className="practice-plant-base" src="/plant-assets/plant-base.png" alt="" />
      {LEAVES.slice(0, visibleLeaves).map((leaf, index) => (
        <img
          className="practice-plant-leaf"
          src="/plant-assets/new-leaf.png"
          alt=""
          key={index}
          style={{ left: leaf.x, top: leaf.y, "--leaf-angle": `${leaf.angle}deg`, "--leaf-order": index }}
        />
      ))}
    </div>
  );
}
