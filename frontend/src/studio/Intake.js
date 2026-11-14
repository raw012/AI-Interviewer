/** Intake: clarify the goal, show the researched interview brief, then set up the interviewer. */
import React, { useCallback, useEffect, useState } from "react";
import { IconCheck, IconExternalLink, IconRefresh, IconVolume, IconUpload } from "@tabler/icons-react";
import { api } from "./api";
import { speak } from "./audio";
import Avatar, { createLevelBus } from "./Avatar";
import { Badge, Spinner } from "./ui";

const LENGTHS = [15, 30, 45, 60];

function Question({ q, onAnswer }) {
  const [custom, setCustom] = useState("");
  return (
    <div className="bubble bubble--ai">
      <p>{q.question}</p>
      <div className="chips">
        {q.options.map((o) => <button key={o.value} className="chip-btn" onClick={() => onAnswer(q.field, o.value)}>{o.label}</button>)}
      </div>
      {q.free_text && (
        <form className="row inline-form" onSubmit={(e) => { e.preventDefault(); if (custom.trim()) onAnswer(q.field, custom.trim()); }}>
          <input value={custom} onChange={(e) => setCustom(e.target.value)} placeholder="Another company" />
          <button className="btn btn-soft">Use</button>
        </form>
      )}
    </div>
  );
}

function PersonaCard({ persona, selected, onSelect, voicePref }) {
  const [bus] = useState(createLevelBus);
  const [playing, setPlaying] = useState(false);
  async function preview(event) {
    event.stopPropagation();
    setPlaying(true);
    await speak(`Hi, I'm ${persona.name.split(" ")[0]}. ${persona.style.split(".")[0]}.`, {
      persona: persona.key, voice: voicePref, gender: persona.voices.browser, onLevel: bus.emit,
    });
    setPlaying(false);
  }
  return (
    <button type="button" className={`persona${selected ? " is-selected" : ""}`} onClick={onSelect} aria-pressed={selected}>
      <div className="persona-face"><Avatar persona={persona} state={playing ? "speaking" : "idle"} bus={bus} /></div>
      <strong>{persona.name}</strong>
      <span className="muted small">{persona.title}</span>
      <span className="persona-style">{persona.style}</span>
      <span className="link small" role="button" tabIndex={0} onClick={preview} onKeyDown={(e) => e.key === "Enter" && preview(e)}>
        <IconVolume size={15} /> {playing ? "Playing…" : "Hear voice"}
      </span>
    </button>
  );
}

export default function Intake({ draft, config, profile, go, onStarted, refreshProfile }) {
  const [stage, setStage] = useState("parsing");
  const [target, setTarget] = useState(draft?.target || null);
  const [missing, setMissing] = useState([]);
  const [answers, setAnswers] = useState([]);
  const [brief, setBrief] = useState(null);
  const [rounds, setRounds] = useState([]);
  const [minutes, setMinutes] = useState(30);
  const [persona, setPersona] = useState(profile?.prefs?.persona || "maya");
  const [pressure, setPressure] = useState(profile?.prefs?.pressure || "realistic");
  const [resume, setResume] = useState(null);
  const [error, setError] = useState("");
  const [editing, setEditing] = useState(false);

  const loadBrief = useCallback(async (t, refresh = false) => {
    setStage("researching");
    setError("");
    try {
      const { brief: b } = await api.post("/studio/intake/brief", { target: t, refresh });
      setBrief(b);
      setRounds(b.loop.map((x, i) => `${i}:${x.round}`));
      setStage("brief");
    } catch (e) { setError(e.message); setStage("brief-error"); }
  }, []);

  useEffect(() => {
    api.get("/resume/status").then(setResume).catch(() => {});
    if (draft?.target) { loadBrief(draft.target); return; }
    if (!draft?.text) { go("/"); return; }
    api.post("/studio/intake/parse", { text: draft.text, job_description: draft.job_description || "" })
      .then((r) => {
        setTarget(r.target);
        setMissing(r.missing);
        if (r.missing.length) setStage("clarify");
        else loadBrief(r.target);
      })
      .catch((e) => { setError(e.message); setStage("parse-error"); });
  }, [draft, go, loadBrief]);

  async function answer(field, value) {
    const q = missing.find((m) => m.field === field);
    const label = q?.options.find((o) => o.value === value)?.label || value;
    setAnswers((a) => [...a, { q: q?.question, a: label }]);
    const r = await api.post("/studio/intake/answer", { target, answers: { [field]: value } });
    setTarget(r.target);
    setMissing(r.missing);
    if (!r.missing.length) loadBrief(r.target);
  }

  async function uploadResume(file) {
    if (!file) return;
    const form = new FormData();
    form.append("file", file);
    try {
      await api.upload("/resume", form);
      setResume({ has_resume: true, filename: file.name });
    } catch (e) { setError(e.message); }
  }

  async function start() {
    setStage("starting");
    setError("");
    try {
      await api.put("/studio/profile", { prefs: { persona, pressure } });
      const started = await api.post("/studio/interviews", { target: { ...target, rounds: rounds.map((x) => x.split(":")[1]) }, brief, minutes, persona });
      refreshProfile?.();
      onStarted(started);
      go(`/room/${started.session_id}`);
    } catch (e) { setError(e.message); setStage("brief"); }
  }

  const summary = target && [target.company, target.role_title || config?.roles?.find((r) => r.key === target.role_family)?.label, config?.levels?.find((l) => l.key === target.level)?.label, target.level === "intern" ? "" : target.employment === "internship" ? "Internship" : target.employment === "full_time" ? "Full-time" : ""].filter(Boolean).join(" · ");

  return (
    <div className="page intake">
      <div className="thread">
        {draft?.text && <div className="bubble bubble--me">{draft.text}</div>}
        {stage === "parsing" && <div className="bubble bubble--ai"><Spinner label="Reading your goal…" /></div>}
        {target && stage !== "parsing" && summary && <div className="bubble bubble--ai">Got it: <strong>{summary}</strong>{missing.length ? ". A couple of quick questions so the interview matches the real thing." : "."}</div>}
        {answers.map((x, i) => (
          <React.Fragment key={i}>
            <div className="bubble bubble--ai muted">{x.q}</div>
            <div className="bubble bubble--me">{x.a}</div>
          </React.Fragment>
        ))}
        {stage === "clarify" && missing[0] && <Question q={missing[0]} onAnswer={answer} />}
        {stage === "researching" && <div className="bubble bubble--ai"><Spinner label={`Looking up how ${target?.company || "this"} interviews for this role…`} /></div>}
        {(stage === "parse-error" || stage === "brief-error") && (
          <div className="bubble bubble--ai error">{error} <button className="link" onClick={() => (stage === "brief-error" ? loadBrief(target) : go("/"))}>Try again</button></div>
        )}
      </div>

      {brief && (stage === "brief" || stage === "starting") && (
        <>
          <section className="card brief">
            <div className="brief-head">
              <div>
                <p className="eyebrow">Your interview brief</p>
                <h2>{brief.company ? `${brief.company} · ` : ""}{brief.role_label} · {brief.level_label}</h2>
              </div>
              <div className="row">
                <Badge tone={brief.confidence === "high" ? "good" : brief.confidence === "medium" ? "warm" : "cool"}>{brief.confidence} confidence</Badge>
                <button className="icon-btn" title="Research again" onClick={() => loadBrief(target, true)}><IconRefresh size={16} /></button>
              </div>
            </div>
            <p>{brief.summary}</p>
            {brief.trending && (
              <div className="trend-box">
                <strong>Coding topics candidates reported in the last 30 days</strong>
                <div className="chips">{brief.trending.topics.map((t) => <Badge key={t} tone="warm">{t}</Badge>)}</div>
                <span className="small muted">{Object.entries(brief.trending.difficulty_mix).map(([k, v]) => `${v} ${k.toLowerCase()}`).join(" · ")} among the top {brief.trending.count} reported problems. Coding rounds here will favour these.</span>
              </div>
            )}
            <h4>Rounds to practise <span className="muted small">tap to include or skip</span></h4>
            <div className="rounds">
              {brief.loop.map((r, i) => {
                const slot = `${i}:${r.round}`;
                const on = rounds.includes(slot);
                return (
                  <button key={slot} className={`round${on ? " is-on" : ""}`} onClick={() => setRounds(on ? rounds.filter((x) => x !== slot) : [...rounds, slot])}>
                    <span className="round-check">{on && <IconCheck size={14} />}</span>
                    <strong>{r.label}</strong>
                    <span className="small muted">{r.focus}</span>
                  </button>
                );
              })}
              {(config?.rounds || []).filter((r) => !brief.loop.some((l) => l.round === r.key) && ["behavioral", "coding", "system_design", "resume_deep_dive"].includes(r.key)).map((r) => (
                <button key={r.key} className={`round round--extra${rounds.includes(`x:${r.key}`) ? " is-on" : ""}`} onClick={() => setRounds(rounds.includes(`x:${r.key}`) ? rounds.filter((x) => x !== `x:${r.key}`) : [...rounds, `x:${r.key}`])}>
                  <span className="round-check">{rounds.includes(`x:${r.key}`) && <IconCheck size={14} />}</span>
                  <strong>+ {r.label}</strong>
                </button>
              ))}
            </div>
            <div className="brief-cols">
              <div>
                <h4>What they look for</h4>
                <ul>{brief.look_for.map((x) => <li key={x}>{x}</li>)}</ul>
              </div>
              <div>
                <h4>Prep tips</h4>
                <ul>{brief.tips.filter(Boolean).map((x) => <li key={x}>{x}</li>)}</ul>
              </div>
            </div>
            {brief.sources?.length > 0 && (
              <details className="sources">
                <summary>{brief.sources.length} sources{brief.search_used ? " · includes live search" : ""}</summary>
                <ul>{brief.sources.map((s) => <li key={s.url}><a href={s.url} target="_blank" rel="noreferrer">{s.label} <IconExternalLink size={13} /></a></li>)}</ul>
                <p className="small muted">Questions are labelled as official guidance, commonly reported by candidates, or practice. We never claim a company asked a question unless a source says so.</p>
              </details>
            )}
            <button className="link small" onClick={() => setEditing(!editing)}>{editing ? "Done editing" : "Something's off? Edit details"}</button>
            {editing && (
              <div className="edit-grid">
                <label>Company<input value={target.company || ""} onChange={(e) => setTarget({ ...target, company: e.target.value })} /></label>
                <label>Role<select value={target.role_family || ""} onChange={(e) => setTarget({ ...target, role_family: e.target.value })}>{config.roles.map((r) => <option key={r.key} value={r.key}>{r.label}</option>)}</select></label>
                <label>Level<select value={target.level || ""} onChange={(e) => setTarget({ ...target, level: e.target.value, employment: e.target.value === "intern" ? "internship" : "full_time" })}>{config.levels.map((l) => <option key={l.key} value={l.key}>{l.label}</option>)}</select></label>
                <button className="btn btn-soft" onClick={() => { setEditing(false); loadBrief(target, true); }}>Update brief</button>
              </div>
            )}
          </section>

          <section className="card setup">
            <h2>Choose your interviewer</h2>
            <div className="personas">
              {config.personas.map((p) => <PersonaCard key={p.key} persona={p} selected={persona === p.key} onSelect={() => setPersona(p.key)} voicePref={profile?.prefs?.voice} />)}
            </div>
            <div className="setup-row">
              <div>
                <h4>Interview style</h4>
                <div className="segmented">
                  {config.pressures.map((p) => <button key={p.key} className={pressure === p.key ? "is-on" : ""} onClick={() => setPressure(p.key)} title={p.description}>{p.key[0].toUpperCase() + p.key.slice(1)}</button>)}
                </div>
                <p className="small muted">{config.pressures.find((p) => p.key === pressure)?.description}</p>
              </div>
              <div>
                <h4>Length</h4>
                <div className="segmented">{LENGTHS.map((m) => <button key={m} className={minutes === m ? "is-on" : ""} onClick={() => setMinutes(m)}>{m} min</button>)}</div>
              </div>
              <div>
                <h4>Resume</h4>
                {resume?.has_resume ? <p className="small">Using <strong>{resume.filename}</strong> for project questions.</p> : <p className="small muted">Optional. Adds questions about your own projects.</p>}
                <label className="btn btn-soft file-btn"><IconUpload size={16} /> {resume?.has_resume ? "Replace PDF" : "Upload PDF"}<input type="file" accept="application/pdf" onChange={(e) => uploadResume(e.target.files[0])} /></label>
              </div>
            </div>
            {error && <p className="error">{error}</p>}
            <div className="start-row">
              <p className="small muted">Tip: find a quiet spot and use headphones. You can type any answer instead of speaking.</p>
              <button className="btn btn-primary btn-lg" disabled={stage === "starting" || !rounds.length} onClick={start}>{stage === "starting" ? "Preparing your interview…" : "Start interview"}</button>
            </div>
          </section>
        </>
      )}
    </div>
  );
}
