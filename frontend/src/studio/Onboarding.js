/** First-visit animated tour: four short scenes explaining the practice loop. */
import React, { useEffect, useState } from "react";
import Avatar, { createLevelBus } from "./Avatar";

const SCENES = [
  {
    title: "Tell us what you're preparing for",
    body: "Type it the way you'd say it: \"Google SWE intern, interviews in three weeks.\" We'll ask only for what's missing.",
    visual: "goal",
  },
  {
    title: "We look up the real interview",
    body: "You get a short brief on the company's loop for your role and level, with sources. Check it, tweak it, and start.",
    visual: "brief",
  },
  {
    title: "Talk to an interviewer who listens",
    body: "Answer out loud or type. Your interviewer follows up on what you actually said, like a real one would.",
    visual: "room",
  },
  {
    title: "Get coached, then get better",
    body: "After each interview you'll see what worked, what was missing, and guiding questions to build a stronger answer. Your next session picks up where you need it most.",
    visual: "report",
  },
];

function SceneVisual({ kind, persona }) {
  const [bus] = useState(createLevelBus);
  useEffect(() => {
    if (kind !== "room") return undefined;
    let t = 0;
    const id = setInterval(() => { t += 1; bus.emit(Math.abs(Math.sin(t / 2.2)) * 0.8 * (t % 18 < 12 ? 1 : 0)); }, 90);
    return () => clearInterval(id);
  }, [kind, bus]);
  if (kind === "goal") {
    return (
      <div className="tour-goal">
        <div className="tour-typing">Google SWE intern, interviews in 3 weeks<span className="caret" /></div>
        <div className="tour-chips"><span>Internship ✓</span><span>Google ✓</span><span>Software Engineering ✓</span></div>
      </div>
    );
  }
  if (kind === "brief") {
    return (
      <div className="tour-brief">
        {["Coding · 45 min", "Coding · 45 min", "Googleyness · 45 min"].map((x, i) => <div key={i} className="tour-round" style={{ animationDelay: `${i * 0.25}s` }}>{x}</div>)}
        <div className="tour-source">3 sources · checked today</div>
      </div>
    );
  }
  if (kind === "room") {
    return (
      <div className="tour-room">
        <div className="tour-avatar"><Avatar persona={persona} state="speaking" bus={bus} /></div>
        <div className="tour-caption">"You mentioned caching. What happens when the cache is cold?"</div>
      </div>
    );
  }
  return (
    <div className="tour-report">
      <div className="tour-bar"><span style={{ width: "78%" }} />Communication</div>
      <div className="tour-bar"><span style={{ width: "54%" }} />Impact & results</div>
      <div className="tour-bar"><span style={{ width: "66%" }} />Problem solving</div>
      <div className="tour-question">Think about it: how would your manager have measured that success?</div>
    </div>
  );
}

export default function Onboarding({ persona, onDone }) {
  const [index, setIndex] = useState(0);
  const scene = SCENES[index];
  const last = index === SCENES.length - 1;
  useEffect(() => {
    const onKey = (e) => {
      if (e.key === "ArrowRight") setIndex((i) => Math.min(SCENES.length - 1, i + 1));
      if (e.key === "ArrowLeft") setIndex((i) => Math.max(0, i - 1));
      if (e.key === "Escape") onDone();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onDone]);
  return (
    <div className="tour" role="dialog" aria-modal="true" aria-label="Welcome tour">
      <div className="tour-card">
        <div className="tour-visual" key={scene.visual}><SceneVisual kind={scene.visual} persona={persona} /></div>
        <div className="tour-copy" key={index}>
          <p className="eyebrow">Step {index + 1} of {SCENES.length}</p>
          <h2>{scene.title}</h2>
          <p>{scene.body}</p>
        </div>
        <div className="tour-footer">
          <div className="tour-dots">{SCENES.map((s, i) => <button key={s.title} aria-label={`Step ${i + 1}`} className={i === index ? "active" : ""} onClick={() => setIndex(i)} />)}</div>
          <div className="row">
            <button className="btn btn-ghost" onClick={onDone}>Skip</button>
            <button className="btn btn-primary" onClick={() => (last ? onDone() : setIndex(index + 1))}>{last ? "Let's start" : "Next"}</button>
          </div>
        </div>
      </div>
    </div>
  );
}
