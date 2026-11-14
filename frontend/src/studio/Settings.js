/** Settings: profile, interviewer voice and style, AI providers, resume, privacy and account. */
import React, { useEffect, useState } from "react";
import { IconVolume, IconUpload } from "@tabler/icons-react";
import { api, tokenStore } from "./api";
import { speak } from "./audio";
import { Badge, formatDate } from "./ui";

function Section({ id, title, children, note }) {
  return (
    <section id={id} className="card settings-section">
      <h2>{title}</h2>
      {note && <p className="small muted">{note}</p>}
      {children}
    </section>
  );
}

function Providers() {
  const [data, setData] = useState(null);
  const [keys, setKeys] = useState({});
  const [msg, setMsg] = useState({});
  const load = () => api.get("/settings/providers").then(setData).catch(() => {});
  useEffect(() => { load(); }, []);
  async function save(provider) {
    setMsg({ ...msg, [provider]: "Checking…" });
    try {
      await api.post(`/settings/providers/${provider}/test`, { api_key: keys[provider] });
      await api.put(`/settings/providers/${provider}/key`, { api_key: keys[provider] });
      setKeys({ ...keys, [provider]: "" });
      setMsg({ ...msg, [provider]: "Connected" });
      load();
    } catch (e) { setMsg({ ...msg, [provider]: e.message }); }
  }
  async function remove(provider) {
    await api.del(`/settings/providers/${provider}/key`);
    load();
  }
  async function setActive(field, value) {
    await api.put("/settings/providers/active", { llm_provider: data.llm_provider, transcription_provider: data.transcription_provider, [field]: value });
    load();
  }
  if (!data) return null;
  const chat = data.providers.filter((p) => p.chat);
  const stt = data.providers.filter((p) => p.transcription);
  return (
    <>
      <div className="row wrap">
        <label>Thinking model
          <select value={data.llm_provider} onChange={(e) => setActive("llm_provider", e.target.value)}>
            {chat.map((p) => <option key={p.key} value={p.key}>{p.name} · {p.model}</option>)}
          </select>
        </label>
        <label>Speech to text
          <select value={data.transcription_provider} onChange={(e) => setActive("transcription_provider", e.target.value)}>
            {stt.map((p) => <option key={p.key} value={p.key}>{p.name}</option>)}
          </select>
        </label>
      </div>
      <ul className="providers">
        {data.providers.map((p) => (
          <li key={p.key}>
            <div>
              <strong>{p.name}</strong>
              <span className="small muted">{[p.chat && "interviewer", p.transcription && "speech-to-text", (p.tts || p.key === "groq") && "voice"].filter(Boolean).join(" · ")}</span>
            </div>
            {p.configured ? (
              <div className="row"><Badge tone="good">Connected {p.masked}</Badge><button className="link small" onClick={() => remove(p.key)}>Remove</button></div>
            ) : p.server_fallback_available ? (
              <Badge tone="cool">Provided by server</Badge>
            ) : (
              <form className="row" onSubmit={(e) => { e.preventDefault(); save(p.key); }}>
                <input type="password" placeholder="Paste API key" value={keys[p.key] || ""} onChange={(e) => setKeys({ ...keys, [p.key]: e.target.value })} autoComplete="off" />
                <button className="btn btn-soft btn-sm" disabled={(keys[p.key] || "").length < 12}>Connect</button>
              </form>
            )}
            {msg[p.key] && <span className="small muted">{msg[p.key]}</span>}
          </li>
        ))}
      </ul>
      <p className="small muted">Keys are encrypted on the server and never shown again. Groq covers thinking, speech-to-text and voices on its free tier; ElevenLabs adds premium voices.</p>
    </>
  );
}

export default function Settings({ config, profile, refreshProfile, user, onSignOut, replayTour }) {
  const prefs = profile?.prefs || {};
  const [voices, setVoices] = useState([]);
  const [account, setAccount] = useState(null);
  const [name, setName] = useState(user?.name || "");
  const [password, setPassword] = useState("");
  const [resume, setResume] = useState(null);
  const [notice, setNotice] = useState("");
  const [confirm, setConfirm] = useState("");

  useEffect(() => {
    api.get("/studio/voices").then((d) => setVoices(d.voices)).catch(() => {});
    api.get("/studio/account").then(setAccount).catch(() => {});
    api.get("/resume/status").then(setResume).catch(() => {});
    if (window.location.hash.includes("#providers")) setTimeout(() => document.getElementById("providers")?.scrollIntoView({ behavior: "smooth" }), 200);
  }, []);

  async function setPref(key, value) {
    await api.put("/studio/profile", { prefs: { [key]: value } });
    refreshProfile();
  }
  async function preview(voice) {
    const persona = config.personas.find((p) => p.key === prefs.persona) || config.personas[0];
    await speak("Thanks for joining. Tell me about a project you're proud of.", { persona: persona.key, voice, gender: persona.voices.browser });
  }
  async function saveAccount(e) {
    e.preventDefault();
    try {
      await api.patch("/studio/account", { name, ...(password ? { new_password: password } : {}) });
      setPassword("");
      setNotice("Saved");
      refreshProfile();
    } catch (err) { setNotice(err.message); }
  }
  async function uploadResume(file) {
    const form = new FormData();
    form.append("file", file);
    try { await api.upload("/resume", form); setResume({ has_resume: true, filename: file.name }); } catch (e) { setNotice(e.message); }
  }
  async function exportData() {
    const data = await api.get("/studio/account/export");
    const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }));
    const a = Object.assign(document.createElement("a"), { href: url, download: "ai-interviewer-data.json" });
    a.click();
    URL.revokeObjectURL(url);
  }
  async function deleteAccount() {
    try {
      await api.del("/studio/account", { confirm });
      tokenStore.set("");
      onSignOut();
    } catch (e) { setNotice(e.message); }
  }

  const acc = account?.account;
  return (
    <div className="page settings">
      <h1 className="page-title">Settings</h1>
      <Section title="Interviewer">
        <div className="settings-grid">
          <label>Default interviewer
            <select value={prefs.persona} onChange={(e) => setPref("persona", e.target.value)}>
              {config.personas.map((p) => <option key={p.key} value={p.key}>{p.name} · {p.title}</option>)}
            </select>
          </label>
          <label>Style
            <select value={prefs.pressure} onChange={(e) => setPref("pressure", e.target.value)}>
              {config.pressures.map((p) => <option key={p.key} value={p.key}>{p.key[0].toUpperCase() + p.key.slice(1)}</option>)}
            </select>
          </label>
          <label>Answer by
            <select value={prefs.answer_mode} onChange={(e) => setPref("answer_mode", e.target.value)}>
              <option value="voice">Voice</option>
              <option value="text">Typing</option>
            </select>
          </label>
        </div>
        <h4>Voice</h4>
        <div className="voices">
          <button className={`voice${prefs.voice === "auto" ? " is-on" : ""}`} onClick={() => setPref("voice", "auto")}>
            <strong>Match interviewer</strong><span className="small muted">Each interviewer has their own voice</span>
          </button>
          {voices.map((v) => (
            <div key={v.id} className={`voice${prefs.voice === v.id ? " is-on" : ""}${v.available ? "" : " is-off"}`}>
              <button className="voice-pick" onClick={() => v.available && setPref("voice", v.id)} disabled={!v.available}>
                <strong>{v.label}</strong><span className="small muted">{v.description}</span>
                {!v.available && <span className="small muted">Needs a {v.provider === "groq" ? "Groq" : "ElevenLabs"} key</span>}
              </button>
              {v.available && <button className="icon-btn" aria-label={`Preview ${v.label}`} onClick={() => preview(v.id)}><IconVolume size={15} /></button>}
            </div>
          ))}
        </div>
        <div className="toggles">
          {[["auto_listen", "Start listening automatically after each question"], ["show_captions", "Show captions"], ["speak_feedback", "Offer spoken debrief after interviews"]].map(([key, label]) => (
            <label key={key} className="switch"><input type="checkbox" checked={!!prefs[key]} onChange={(e) => setPref(key, e.target.checked)} /><span>{label}</span></label>
          ))}
        </div>
      </Section>

      <Section id="providers" title="AI providers" note="Your interviewer runs on the model you connect. Nothing is shared with other users.">
        <Providers />
      </Section>

      <Section title="Resume" note="Used to ask about your own projects. Stored privately; delete it any time.">
        {resume?.has_resume ? <p>Current: <strong>{resume.filename}</strong> {resume.updated_at && <span className="muted small">· {formatDate(resume.updated_at)}</span>}</p> : <p className="muted">No resume uploaded.</p>}
        <div className="row">
          <label className="btn btn-soft file-btn"><IconUpload size={16} /> Upload PDF<input type="file" accept="application/pdf" onChange={(e) => e.target.files[0] && uploadResume(e.target.files[0])} /></label>
          {resume?.has_resume && <button className="link danger" onClick={async () => { await api.del("/resume"); setResume({ has_resume: false }); }}>Delete resume</button>}
        </div>
      </Section>

      <Section title="Account">
        {acc && <p className="small muted">{acc.email} · {acc.google_linked ? "Google linked · " : ""}member since {formatDate(acc.created_at)} · {acc.completed_interviews} interviews · {account.usage.prompt_tokens + account.usage.completion_tokens} tokens used</p>}
        <form className="settings-grid" onSubmit={saveAccount}>
          <label>Name<input value={name} onChange={(e) => setName(e.target.value)} /></label>
          <label>{acc?.has_password ? "New password" : "Set a password"}<input type="password" minLength={8} value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="new-password" placeholder="Leave blank to keep" /></label>
          <button className="btn btn-soft">Save</button>
        </form>
        {notice && <p className="small">{notice}</p>}
        <div className="row wrap">
          <button className="btn btn-ghost btn-sm" onClick={replayTour}>Replay welcome tour</button>
          <button className="btn btn-ghost btn-sm" onClick={async () => { const r = await api.post("/studio/account/sign-out-others"); setNotice(`Signed out ${r.revoked} other session(s)`); }}>Sign out other devices</button>
          <button className="btn btn-ghost btn-sm" onClick={exportData}>Download my data</button>
        </div>
      </Section>

      <Section title="Delete account" note="Permanently deletes your account, interviews, feedback, memory, resume and keys.">
        <div className="row">
          <input value={confirm} onChange={(e) => setConfirm(e.target.value)} placeholder="Type your email to confirm" />
          <button className="btn btn-danger btn-sm" disabled={confirm.trim().toLowerCase() !== (user?.email || "").toLowerCase()} onClick={deleteAccount}>Delete permanently</button>
        </div>
      </Section>
    </div>
  );
}
