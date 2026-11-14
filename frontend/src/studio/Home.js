/** Home: one text box for the goal, plus progress, focus areas and recent sessions. */
import React, { useEffect, useRef, useState } from "react";
import { IconArrowRight, IconMicrophone, IconPlayerStopFilled, IconFileDescription } from "@tabler/icons-react";
import { api } from "./api";
import { startRecording, transcribe } from "./audio";
import PracticePlant from "../PracticePlant";
import { Badge, formatDate, READINESS } from "./ui";

const EXAMPLES = [
  "Google software engineering intern, interviews in three weeks",
  "Meta product data scientist, mid-level, mostly SQL and product sense",
  "Amazon SDE II, want to sharpen Leadership Principles stories",
  "New grad frontend role at a startup, React heavy",
  "Senior ML engineer, ML system design round next Friday",
];

export default function Home({ user, config, profile, go, setDraft, providerReady }) {
  const [text, setText] = useState("");
  const [jd, setJd] = useState("");
  const [showJd, setShowJd] = useState(false);
  const [progress, setProgress] = useState(null);
  const [recent, setRecent] = useState([]);
  const [recording, setRecording] = useState(null);
  const [dictating, setDictating] = useState(false);
  const [placeholder, setPlaceholder] = useState(0);
  const [error, setError] = useState("");
  const inputRef = useRef(null);

  useEffect(() => {
    api.get("/studio/progress").then(setProgress).catch(() => {});
    api.get("/studio/interviews").then((d) => setRecent(d.interviews.slice(0, 4))).catch(() => {});
    const id = setInterval(() => setPlaceholder((p) => (p + 1) % EXAMPLES.length), 3800);
    return () => clearInterval(id);
  }, []);

  function submit(event) {
    event?.preventDefault();
    if (text.trim().length < 3) { inputRef.current?.focus(); return; }
    setDraft({ text: text.trim(), job_description: jd.trim() });
    go("/new");
  }

  async function toggleDictation() {
    setError("");
    if (recording) {
      const rec = recording;
      setRecording(null);
      setDictating(true);
      try {
        const blob = await rec.stop();
        const said = await transcribe(blob);
        setText((t) => (t ? `${t} ${said}` : said));
      } catch (e) { setError(e.message); }
      setDictating(false);
      return;
    }
    try { setRecording(await startRecording()); } catch { setError("Microphone access was blocked. You can type instead."); }
  }

  const last = profile?.target?.company || profile?.target?.role_family ? profile.target : null;
  const firstName = (user?.name || "").split(" ")[0];
  const focus = progress?.focus || [];
  return (
    <div className="page home">
      <section className="hero">
        <p className="eyebrow">{firstName ? `Hi ${firstName}` : "Welcome"}</p>
        <h1>What are you preparing for?</h1>
        <form className="goal" onSubmit={submit}>
          <textarea
            ref={inputRef}
            value={text}
            rows={3}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) submit(e); }}
            placeholder={EXAMPLES[placeholder]}
            aria-label="Describe the interview you're preparing for"
          />
          {showJd && (
            <textarea className="goal-jd" rows={5} value={jd} onChange={(e) => setJd(e.target.value)} placeholder="Paste the job description (optional). It helps tailor questions to the team." />
          )}
          <div className="goal-actions">
            <div className="row">
              <button type="button" className={`icon-btn${recording ? " is-live" : ""}`} onClick={toggleDictation} aria-label={recording ? "Stop dictation" : "Dictate"} title={recording ? "Stop" : "Say it instead"} disabled={dictating}>
                {recording ? <IconPlayerStopFilled size={18} /> : <IconMicrophone size={18} />}
              </button>
              <button type="button" className="chip-btn" onClick={() => setShowJd(!showJd)}><IconFileDescription size={16} /> {showJd ? "Hide job description" : "Add job description"}</button>
              {dictating && <span className="muted small">Transcribing…</span>}
            </div>
            <button className="btn btn-primary" disabled={!text.trim()}>Continue <IconArrowRight size={18} /></button>
          </div>
        </form>
        {error && <p className="error">{error}</p>}
        <div className="examples">
          {EXAMPLES.slice(0, 3).map((x) => <button key={x} className="chip-btn" onClick={() => setText(x)}>{x}</button>)}
        </div>
        {!providerReady && (
          <div className="notice">
            <strong>One setup step:</strong> connect an AI provider key (Groq has a free tier) so your interviewer can think and speak.
            <button className="link" onClick={() => go("/settings#providers")}>Connect a key</button>
          </div>
        )}
      </section>

      <section className="home-grid">
        <div className="card plant-card">
          <PracticePlant completed={progress?.completed || 0} />
          <div>
            <h3>{progress?.completed || 0} interview{progress?.completed === 1 ? "" : "s"} completed</h3>
            <p className="muted">Each finished interview grows a leaf.</p>
            {last && (
              <button className="btn btn-soft" onClick={() => { setDraft({ target: last }); go("/new"); }}>
                Practise again: {[last.company, last.role_title].filter(Boolean).join(" · ") || "last target"}
              </button>
            )}
          </div>
        </div>
        <div className="card">
          <h3>What I'll focus on next</h3>
          {focus.length ? (
            <div className="chips">{focus.map((f) => <Badge key={f} tone="violet">{config?.competencies?.[f] || f}</Badge>)}</div>
          ) : (
            <p className="muted">After your first interview, I'll keep track of the skills worth practising and bring them back at the right time.</p>
          )}
          <button className="link" onClick={() => go("/memory")}>See what I remember</button>
        </div>
        <div className="card recent">
          <h3>Recent interviews</h3>
          {recent.length === 0 && <p className="muted">Nothing yet. Your sessions and feedback will appear here.</p>}
          {recent.map((r) => (
            <button key={r.session_id} className="recent-row" onClick={() => go(r.status === "completed" ? `/report/${r.session_id}` : `/room/${r.session_id}`)}>
              <span>
                <strong>{r.title}</strong>
                <span className="muted small">{formatDate(r.created_at)} · {r.exchanges} answers</span>
              </span>
              {r.status === "completed" ? <Badge tone={READINESS[r.verdict]?.tone || "cool"}>{Number(r.overall_score || 0).toFixed(1)}</Badge> : <Badge tone="warm">Resume</Badge>}
            </button>
          ))}
          {recent.length > 0 && <button className="link" onClick={() => go("/history")}>All history</button>}
        </div>
      </section>
    </div>
  );
}
