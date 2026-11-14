/** Interview room: video-call layout with a speaking avatar, voice or typed answers, code pad and hints. */
import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  IconBulb, IconCode, IconKeyboard, IconMessageCircle, IconMicrophone, IconPlayerStopFilled,
  IconRepeat, IconSend, IconPhoneOff, IconBadgeCc, IconVolume, IconVolumeOff,
} from "@tabler/icons-react";
import { api } from "./api";
import { primeAudio, speak, startRecording, transcribe } from "./audio";
import Avatar, { createLevelBus } from "./Avatar";
import CodeWorkspace from "./CodeWorkspace";
import { Spinner } from "./ui";

const CODE_KINDS = new Set(["coding", "sql", "frontend", "object_design"]);
const FINISH_STEPS = ["Reviewing each answer against its rubric…", "Looking for patterns across your answers…", "Writing guiding questions for you…", "Planning your next session…"];

function clock(seconds) {
  const s = Math.max(0, seconds | 0);
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

export default function Room({ sessionId, start, config, profile, user, go }) {
  const prefs = profile?.prefs || {};
  const [bus] = useState(createLevelBus);
  const [meterBus] = useState(createLevelBus);
  const [info, setInfo] = useState(start?.session_id === sessionId ? start : null);
  const [persona, setPersona] = useState(null);
  const [line, setLine] = useState(start?.session_id === sessionId ? start.utterance : "");
  const [status, setStatus] = useState("loading"); // loading | ready | speaking | listening | recording | transcribing | thinking | finishing
  const [mode, setMode] = useState(prefs.answer_mode === "text" ? "text" : "voice");
  const [draft, setDraft] = useState("");
  const [code, setCode] = useState("");
  const [run, setRun] = useState(null);
  const [showCode, setShowCode] = useState(false);
  const [captions, setCaptions] = useState(prefs.show_captions !== false);
  const [muted, setMuted] = useState(false);
  const [transcript, setTranscript] = useState(start?.session_id === sessionId ? [{ role: "interviewer", text: start.utterance }] : []);
  const [showTranscript, setShowTranscript] = useState(false);
  const [hint, setHint] = useState("");
  const [error, setError] = useState("");
  const [remaining, setRemaining] = useState(start?.remaining_seconds || 0);
  const [finishStep, setFinishStep] = useState(0);
  const [joined, setJoined] = useState(false);
  const recorder = useRef(null);
  const speechAbort = useRef(null);
  const ending = useRef(false);

  useEffect(() => {
    if (info) return;
    api.get(`/studio/interviews/${sessionId}`).then((d) => {
      if (d.status === "completed" || d.phase === "done") { go(`/report/${sessionId}`); return; }
      setInfo(d);
      setRemaining(d.remaining_seconds || 0);
      setTranscript(d.transcript);
      const lastLine = [...d.transcript].reverse().find((t) => t.role === "interviewer");
      setLine(lastLine?.text || "");
    }).catch((e) => setError(e.message));
  }, [info, sessionId, go]);

  useEffect(() => {
    if (!info || !config) return;
    setPersona(config.personas.find((p) => p.key === info.persona) || config.personas[0]);
    setStatus((s) => (s === "loading" ? "ready" : s));
    if (CODE_KINDS.has(info.current_kind)) setShowCode(true);
  }, [info, config]);

  useEffect(() => {
    if (!remaining) return undefined;
    const id = setInterval(() => setRemaining((r) => Math.max(0, r - 1)), 1000);
    return () => clearInterval(id);
  }, [remaining > 0]); // eslint-disable-line react-hooks/exhaustive-deps

  const say = useCallback(async (text) => {
    if (!text) return;
    speechAbort.current?.abort();
    const controller = new AbortController();
    speechAbort.current = controller;
    setStatus("speaking");
    if (!muted) {
      await speak(text, { persona: persona?.key, voice: prefs.voice, gender: persona?.voices?.browser, onLevel: bus.emit, signal: controller.signal });
    } else {
      await new Promise((r) => setTimeout(r, Math.min(4000, text.length * 35)));
    }
    if (controller.signal.aborted) return;
    setStatus("listening");
  }, [bus, muted, persona, prefs.voice]);

  useEffect(() => {
    if (status === "listening" && mode === "voice" && prefs.auto_listen && !recorder.current && !ending.current) beginRecording();
  }, [status]); // eslint-disable-line react-hooks/exhaustive-deps

  async function join() {
    primeAudio();
    setJoined(true);
    say(line);
  }

  async function beginRecording() {
    setError("");
    speechAbort.current?.abort();
    try {
      recorder.current = await startRecording(meterBus.emit);
      setStatus("recording");
    } catch {
      setError("Microphone access was blocked. You can type your answer instead.");
      setMode("text");
      setStatus("listening");
    }
  }

  async function stopRecording() {
    const rec = recorder.current;
    recorder.current = null;
    if (!rec) return;
    setStatus("transcribing");
    try {
      const blob = await rec.stop();
      const text = await transcribe(blob);
      setDraft((d) => (d ? `${d} ${text}` : text));
      setStatus("listening");
    } catch (e) {
      setError(e.message);
      setStatus("listening");
    }
  }

  async function send(textOverride) {
    const text = (textOverride ?? draft).trim();
    if (!text && !code.trim()) return;
    setError("");
    setHint("");
    setStatus("thinking");
    setTranscript((t) => [...t, { role: "candidate", text, code: showCode ? code : "" }]);
    setDraft("");
    try {
      const result = await api.post(`/studio/interviews/${sessionId}/turn`, { text, code: showCode ? code : "", run: showCode ? run : null });
      setInfo((i) => ({ ...i, ...result }));
      setRemaining(result.remaining_seconds);
      setLine(result.utterance);
      setTranscript((t) => [...t, { role: "interviewer", text: result.utterance }]);
      if (result.action === "next") {
        setCode("");
        setRun(null);
        setShowCode(CODE_KINDS.has(result.current_kind));
      }
      await say(result.utterance);
      if (result.action === "end") finish();
    } catch (e) {
      setError(e.message);
      setDraft(text);
      setTranscript((t) => t.slice(0, -1));
      setStatus("listening");
    }
  }

  async function askHint() {
    try {
      const { hint: h } = await api.post(`/studio/interviews/${sessionId}/hint`);
      setHint(h);
    } catch (e) { setError(e.message); }
  }

  async function finish() {
    if (ending.current) return;
    ending.current = true;
    speechAbort.current?.abort();
    recorder.current?.cancel();
    setStatus("finishing");
    const id = setInterval(() => setFinishStep((s) => Math.min(FINISH_STEPS.length - 1, s + 1)), 2600);
    try {
      await api.post(`/studio/interviews/${sessionId}/finish`);
      go(`/report/${sessionId}`);
    } catch (e) {
      setError(e.message);
      ending.current = false;
      setStatus("listening");
    } finally {
      clearInterval(id);
    }
  }

  function endEarly() {
    if (window.confirm("End the interview now and get feedback on what you've answered so far?")) finish();
  }

  if (!persona || !info) {
    return <div className="room room--loading">{error ? <p className="error">{error}</p> : <Spinner label="Connecting…" />}</div>;
  }

  const avatarState = status === "speaking" ? "speaking" : status === "thinking" ? "thinking" : status === "recording" ? "listening" : "idle";
  const plan = info.plan || [];
  const busy = ["thinking", "transcribing", "finishing"].includes(status);
  const initials = (user?.name || user?.email || "You").split(/[\s@]/).filter(Boolean).slice(0, 2).map((x) => x[0].toUpperCase()).join("");

  return (
    <div className="room">
      <header className="room-bar">
        <div className="room-title">
          <span className="live-dot" />
          <strong>{info.title || "Mock interview"}</strong>
        </div>
        <div className="room-plan" aria-label={`Question ${Math.min((info.index || 0) + 1, info.total)} of ${info.total}`}>
          {plan.map((p, i) => (
            <span key={i} className={`plan-step${i < info.index ? " is-done" : i === info.index ? " is-current" : ""}`} title={p.label} />
          ))}
          <span className="small">{config.rounds.find((r) => r.key === info.current_kind)?.label || ""}</span>
        </div>
        <div className="row">
          {remaining > 0 && <span className={`timer${remaining < 180 ? " is-low" : ""}`}>{clock(remaining)}</span>}
          <button className="btn btn-danger btn-sm" onClick={endEarly} disabled={status === "finishing"}><IconPhoneOff size={16} /> End</button>
        </div>
      </header>

      <main className={`stage${showCode && joined ? " stage--code" : ""}`}>
        {showCode && joined && (
          <CodeWorkspace problem={info.problem || { id: `free-${info.index}`, title: "Scratchpad", text: line }} onChange={({ code: c, run: r }) => { setCode(c); setRun(r); }} />
        )}
        <section className={`tile tile--ai is-${avatarState}`}>
          <div className="tile-avatar"><Avatar persona={persona} state={avatarState} bus={bus} /></div>
          <div className="tile-name">
            <strong>{persona.name}</strong>
            <span>{persona.title}</span>
          </div>
          <div className="tile-state">
            {status === "speaking" && "Speaking"}
            {status === "thinking" && "Thinking…"}
            {status === "recording" && "Listening"}
            {(status === "listening" || status === "ready") && joined && "Your turn"}
          </div>
          {captions && line && joined && <p className="caption" aria-live="polite">{line}</p>}
          {!joined && (
            <div className="join">
              <h2>Ready when you are</h2>
              <p>{persona.name.split(" ")[0]} will speak first. Answer by voice or type, whichever feels natural.</p>
              <button className="btn btn-primary btn-lg" onClick={join}>Join interview</button>
            </div>
          )}
        </section>
        <section className={`tile tile--me${status === "recording" ? " is-recording" : ""}`}>
          <MicRing bus={meterBus} initials={initials} />
          <span className="tile-label">{user?.name?.split(" ")[0] || "You"}</span>
        </section>
        {showTranscript && (
          <aside className="transcript">
            <h3>Transcript</h3>
            {transcript.map((t, i) => (
              <div key={i} className={`tline tline--${t.role}`}>
                <span>{t.role === "interviewer" ? persona.name.split(" ")[0] : "You"}</span>
                <p>{t.text}</p>
                {t.code && <pre>{t.code}</pre>}
              </div>
            ))}
          </aside>
        )}
      </main>

      {status === "finishing" && (
        <div className="overlay">
          <div className="overlay-card">
            <Spinner />
            <h2>Writing your feedback</h2>
            <p>{FINISH_STEPS[finishStep]}</p>
          </div>
        </div>
      )}

      <footer className={`dock${joined ? "" : " is-hidden"}`}>
        {hint && <div className="hint"><IconBulb size={18} /> <span>{hint}</span><button className="link small" onClick={() => setHint("")}>Dismiss</button></div>}
        {error && <p className="error">{error}</p>}
        <div className="answer">
          {mode === "voice" && !draft && status !== "transcribing" ? (
            <div className="voice-row">
              {status === "recording" ? (
                <button className="mic is-live" onClick={stopRecording} aria-label="Stop and review answer"><IconPlayerStopFilled size={26} /></button>
              ) : (
                <button className="mic" onClick={beginRecording} disabled={busy} aria-label="Start answering"><IconMicrophone size={26} /></button>
              )}
              <span className="muted">{status === "recording" ? "Recording… tap to stop and review" : status === "speaking" ? "Tap the mic to interrupt and answer" : busy ? "" : "Tap the mic to answer"}</span>
            </div>
          ) : (
            <div className="text-row">
              <textarea
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                placeholder={status === "transcribing" ? "Transcribing your answer…" : "Type your answer… (Enter to send, Shift+Enter for a new line)"}
                disabled={status === "transcribing"}
                rows={draft.length > 180 ? 5 : 3}
                onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey && !busy) { e.preventDefault(); send(); } }}
              />
              <div className="column">
                <button className="btn btn-primary" onClick={() => send()} disabled={busy || (!draft.trim() && !code.trim())}><IconSend size={17} /> Send</button>
                {mode === "voice" && draft && <button className="btn btn-ghost btn-sm" onClick={() => { setDraft(""); beginRecording(); }}><IconRepeat size={15} /> Re-record</button>}
              </div>
            </div>
          )}
        </div>
        <div className="tools">
          <button className={`tool${mode === "text" ? " is-on" : ""}`} onClick={() => setMode(mode === "voice" ? "text" : "voice")}>{mode === "voice" ? <IconKeyboard size={17} /> : <IconMicrophone size={17} />} {mode === "voice" ? "Type instead" : "Speak instead"}</button>
          <button className={`tool${showCode ? " is-on" : ""}`} onClick={() => setShowCode(!showCode)}><IconCode size={17} /> Code</button>
          <button className="tool" onClick={askHint} disabled={busy}><IconBulb size={17} /> Nudge</button>
          <button className="tool" onClick={() => say(line)} disabled={busy || status === "recording"}><IconRepeat size={17} /> Repeat</button>
          <button className={`tool${captions ? " is-on" : ""}`} onClick={() => setCaptions(!captions)}><IconBadgeCc size={17} /> Captions</button>
          <button className={`tool${muted ? " is-on" : ""}`} onClick={() => { setMuted(!muted); speechAbort.current?.abort(); }}>{muted ? <IconVolumeOff size={17} /> : <IconVolume size={17} />} {muted ? "Muted" : "Sound"}</button>
          <button className={`tool${showTranscript ? " is-on" : ""}`} onClick={() => setShowTranscript(!showTranscript)}><IconMessageCircle size={17} /> Transcript</button>
        </div>
      </footer>
    </div>
  );
}

function MicRing({ bus, initials }) {
  const ref = useRef(null);
  useEffect(() => bus.subscribe((v) => {
    if (ref.current) ref.current.style.setProperty("--level", v.toFixed(3));
  }), [bus]);
  return <div className="mic-ring" ref={ref}><span>{initials}</span></div>;
}
