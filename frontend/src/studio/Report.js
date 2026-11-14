/** Coaching report: readiness, competencies, Socratic per-question coaching, retry, and next-session plan. */
import React, { useEffect, useRef, useState } from "react";
import { IconArrowRight, IconChevronDown, IconExternalLink, IconPlayerPlayFilled, IconPlayerStopFilled, IconMicrophone, IconSparkles } from "@tabler/icons-react";
import { api } from "./api";
import { speak, startRecording, transcribe } from "./audio";
import Avatar, { createLevelBus } from "./Avatar";
import { Badge, PROVENANCE, READINESS, ScoreRing, Spinner, formatDate } from "./ui";

function Retry({ sessionId, question }) {
  const [answer, setAnswer] = useState("");
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [rec, setRec] = useState(null);
  const [error, setError] = useState("");
  async function toggleMic() {
    if (rec) {
      const r = rec;
      setRec(null);
      setBusy(true);
      try { const text = await transcribe(await r.stop()); setAnswer((a) => (a ? `${a} ${text}` : text)); } catch (e) { setError(e.message); }
      setBusy(false);
    } else {
      try { setRec(await startRecording()); } catch { setError("Microphone unavailable. Type instead."); }
    }
  }
  async function submit() {
    setBusy(true);
    setError("");
    try { setResult(await api.post(`/studio/interviews/${sessionId}/retry`, { number: question.number, answer })); } catch (e) { setError(e.message); }
    setBusy(false);
  }
  const delta = result?.score != null ? result.score - question.score : null;
  return (
    <div className="retry">
      <h5>Try it again</h5>
      <p className="small muted">Use the guiding questions above, then answer again. You'll see what improved.</p>
      <textarea rows={4} value={answer} onChange={(e) => setAnswer(e.target.value)} placeholder="Your improved answer…" />
      <div className="row">
        <button className={`icon-btn${rec ? " is-live" : ""}`} onClick={toggleMic} aria-label={rec ? "Stop recording" : "Record answer"}>{rec ? <IconPlayerStopFilled size={16} /> : <IconMicrophone size={16} />}</button>
        <button className="btn btn-primary btn-sm" onClick={submit} disabled={busy || answer.trim().length < 10}>{busy ? "Checking…" : "Compare"}</button>
      </div>
      {error && <p className="error">{error}</p>}
      {result && (
        <div className="retry-result">
          <div className="row">
            <strong>{result.score?.toFixed(1)} / 5</strong>
            {delta != null && <Badge tone={delta > 0 ? "good" : delta < 0 ? "cool" : "warm"}>{delta > 0 ? `+${delta.toFixed(1)}` : delta.toFixed(1)} vs. interview</Badge>}
          </div>
          <p>{result.verdict}</p>
          {result.improved?.length > 0 && <><h6>Better now</h6><ul>{result.improved.map((x) => <li key={x}>{x}</li>)}</ul></>}
          {result.still_missing?.length > 0 && <><h6>Still missing</h6><ul>{result.still_missing.map((x) => <li key={x}>{x}</li>)}</ul></>}
          {result.coach_question && <p className="coach-q">{result.coach_question}</p>}
        </div>
      )}
    </div>
  );
}

function QuestionCard({ q, sessionId, open, onToggle, roundLabel }) {
  const [reveal, setReveal] = useState(false);
  const prov = PROVENANCE[q.provenance] || PROVENANCE.practice;
  return (
    <article className={`qcard${open ? " is-open" : ""}`}>
      <button className="qcard-head" onClick={onToggle} aria-expanded={open}>
        <span className={`qscore qscore--${q.score >= 4 ? "good" : q.score >= 3 ? "warm" : "cool"}`}>{Number(q.score).toFixed(1)}</span>
        <span className="qcard-title">
          <span className="small muted">{roundLabel(q.kind)}</span>
          <strong>{q.question}</strong>
        </span>
        <IconChevronDown size={18} className="chev" />
      </button>
      {open && (
        <div className="qcard-body">
          <div className="row wrap">
            <Badge tone={prov.tone} title={q.source_note}>{prov.label}</Badge>
            {q.source_urls?.slice(0, 2).map((u) => <a key={u} className="small" href={u} target="_blank" rel="noreferrer">source <IconExternalLink size={12} /></a>)}
          </div>
          <div className="exchanges">
            {q.exchanges.map((ex, i) => (
              <div key={i} className="exchange">
                <p className="ex-q">{ex.question}</p>
                <p className="ex-a">{ex.answer || <em className="muted">(no answer)</em>}</p>
                {ex.code && <pre>{ex.code}</pre>}
              </div>
            ))}
          </div>
          <div className="two-col">
            <div><h5>What worked</h5><ul className="ticks">{q.what_worked.map((x) => <li key={x}>{x}</li>)}</ul></div>
            <div><h5>What was missing</h5><ul className="gaps">{q.what_was_missing.map((x) => <li key={x}>{x}</li>)}</ul></div>
          </div>
          {q.coach_questions?.length > 0 && (
            <div className="socratic">
              <h5><IconSparkles size={16} /> Think it through</h5>
              <ol>{q.coach_questions.map((x) => <li key={x}>{x}</li>)}</ol>
            </div>
          )}
          {!reveal ? (
            <button className="btn btn-soft btn-sm" onClick={() => setReveal(true)}>Show a stronger approach</button>
          ) : (
            <div className="outline">
              <h5>A strong answer would</h5>
              <ol>{q.better_outline.map((x) => <li key={x}>{x}</li>)}</ol>
              {q.sample_opening && <blockquote>{q.sample_opening}</blockquote>}
            </div>
          )}
          <Retry sessionId={sessionId} question={q} />
        </div>
      )}
    </article>
  );
}

export default function Report({ sessionId, config, profile, go, setDraft }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [open, setOpen] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [bus] = useState(createLevelBus);
  const abort = useRef(null);
  const persona = config?.personas.find((p) => p.key === data?.persona) || config?.personas?.[0];

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const detail = await api.get(`/studio/interviews/${sessionId}`);
        if (!detail.report) {
          const { report } = await api.post(`/studio/interviews/${sessionId}/finish`);
          detail.report = report;
        }
        if (!cancelled) setData(detail);
      } catch (e) { if (!cancelled) setError(e.message); }
    })();
    return () => { cancelled = true; abort.current?.abort(); };
  }, [sessionId]);

  async function playDebrief() {
    if (playing) { abort.current?.abort(); setPlaying(false); return; }
    const controller = new AbortController();
    abort.current = controller;
    setPlaying(true);
    await speak(data.report.spoken_debrief, { persona: persona.key, voice: profile?.prefs?.voice, gender: persona.voices.browser, onLevel: bus.emit, signal: controller.signal });
    setPlaying(false);
  }

  function practiseNext() {
    const focus = data.report.next_session?.focus || [];
    const names = focus.map((f) => config.competencies[f] || f).join(" and ");
    setDraft({ target: { ...data.target, focus: names ? `Work on ${names}` : "" } });
    go("/new");
  }

  if (error) return <div className="page"><p className="error">{error}</p></div>;
  if (!data) return <div className="page center"><Spinner label="Loading your feedback…" /></div>;
  const { report } = data;
  const readiness = READINESS[report.overall.readiness] || READINESS.developing;
  const roundLabel = (k) => config.rounds.find((r) => r.key === k)?.label || k;

  return (
    <div className="page report">
      <section className="report-hero card">
        <ScoreRing score={report.overall.score} />
        <div className="report-headline">
          <p className="eyebrow">{data.title} · {formatDate(data.created_at)}</p>
          <h1>{report.overall.headline}</h1>
          <Badge tone={readiness.tone}>{readiness.label}</Badge>
          {report.overall.summary && <p>{report.overall.summary}</p>}
        </div>
        <div className="debrief">
          <div className="debrief-face"><Avatar persona={persona} state={playing ? "speaking" : "idle"} bus={bus} /></div>
          <button className="btn btn-soft btn-sm" onClick={playDebrief}>{playing ? <><IconPlayerStopFilled size={15} /> Stop</> : <><IconPlayerPlayFilled size={15} /> Hear {persona.name.split(" ")[0]}'s debrief</>}</button>
        </div>
      </section>

      <div className="report-grid">
        <section className="card">
          <h3>Skills in this interview</h3>
          <div className="bars">
            {report.competencies.map((c) => (
              <div key={c.key} className="bar-row">
                <div className="bar-label"><span>{c.label}</span><strong>{c.score.toFixed(1)}</strong></div>
                <div className="bar"><span style={{ width: `${(c.score / 5) * 100}%` }} className={c.score >= 4 ? "good" : c.score >= 3 ? "warm" : "cool"} /></div>
                {c.next_step && <p className="small muted">{c.next_step}</p>}
              </div>
            ))}
          </div>
        </section>
        <section className="card next">
          <h3>Your next session</h3>
          {report.next_session?.plan && <p>{report.next_session.plan}</p>}
          {report.next_session?.drills?.length > 0 && <><h5>Quick drills</h5><ul>{report.next_session.drills.map((d) => <li key={d}>{d}</li>)}</ul></>}
          {report.patterns?.length > 0 && <><h5>Patterns I noticed</h5><ul>{report.patterns.map((d) => <li key={d}>{d}</li>)}</ul></>}
          <button className="btn btn-primary" onClick={practiseNext}>Practise this next <IconArrowRight size={17} /></button>
        </section>
      </div>

      <section>
        <h2 className="section-title">Question by question</h2>
        {report.questions.map((q, i) => (
          <QuestionCard key={q.number} q={q} sessionId={sessionId} open={open === i} onToggle={() => setOpen(open === i ? -1 : i)} roundLabel={roundLabel} />
        ))}
        {report.questions.length === 0 && <p className="muted">No answers were recorded in this session.</p>}
      </section>
    </div>
  );
}
