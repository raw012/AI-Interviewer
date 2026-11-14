/** Sign in or create an account with email, or continue with Google. */
import React, { useEffect, useRef, useState } from "react";
import { api, tokenStore } from "./api";
import Avatar from "./Avatar";

function useGoogleButton(clientId, onCredential) {
  const ref = useRef(null);
  useEffect(() => {
    if (!clientId || !ref.current) return undefined;
    let cancelled = false;
    const render = () => {
      if (cancelled || !window.google?.accounts?.id) return;
      window.google.accounts.id.initialize({ client_id: clientId, callback: (r) => onCredential(r.credential), ux_mode: "popup" });
      window.google.accounts.id.renderButton(ref.current, { theme: "outline", size: "large", shape: "pill", width: 320, text: "continue_with" });
    };
    if (window.google?.accounts?.id) render();
    else {
      const script = document.createElement("script");
      script.src = "https://accounts.google.com/gsi/client";
      script.async = true;
      script.onload = render;
      document.head.appendChild(script);
    }
    return () => { cancelled = true; };
  }, [clientId, onCredential]);
  return ref;
}

export default function Auth({ config, onSignedIn }) {
  const [mode, setMode] = useState("signup");
  const [form, setForm] = useState({ name: "", email: "", password: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const finish = (data) => { tokenStore.set(data.token); onSignedIn(data.user); };
  const googleRef = useGoogleButton(config?.google_client_id, async (credential) => {
    setError("");
    try { finish(await api.post("/auth/google", { credential })); } catch (e) { setError(e.message); }
  });

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const data = await api.post(mode === "signup" ? "/auth/register" : "/auth/login", form);
      finish(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  const personas = config?.personas || [];
  return (
    <main className="auth">
      <section className="auth-story" aria-hidden="true">
        <div className="auth-faces">
          {personas.slice(0, 3).map((p, i) => (
            <div key={p.key} className={`auth-face auth-face--${i}`}><Avatar persona={p} state="idle" /></div>
          ))}
        </div>
        <h2>Practise with interviewers who listen, follow up, and remember.</h2>
        <ul>
          <li>Questions matched to the company, role and level you're targeting</li>
          <li>Real-time follow-ups on what you actually said</li>
          <li>Coaching that shows you how to answer better next time</li>
        </ul>
      </section>
      <section className="auth-panel">
        <div className="brand"><span className="brand-mark">AI</span> Interviewer</div>
        <h1>{mode === "signup" ? "Create your account" : "Welcome back"}</h1>
        <p className="muted">{mode === "signup" ? "Free to try. Your practice history stays private to you." : "Sign in to continue practising."}</p>
        {config?.google_client_id && (
          <>
            <div className="google-slot" ref={googleRef} />
            <div className="divider"><span>or with email</span></div>
          </>
        )}
        <form onSubmit={submit} className="stack">
          {mode === "signup" && (
            <label>Name<input autoComplete="name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="What should the interviewer call you?" /></label>
          )}
          <label>Email<input type="email" required autoComplete="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></label>
          <label>Password<input type="password" required minLength={6} autoComplete={mode === "signup" ? "new-password" : "current-password"} value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} /></label>
          {error && <p className="error" role="alert">{error}</p>}
          <button className="btn btn-primary btn-lg" disabled={busy}>{busy ? "One moment…" : mode === "signup" ? "Create account" : "Sign in"}</button>
        </form>
        <p className="auth-switch">
          {mode === "signup" ? "Already have an account?" : "New here?"}
          <button type="button" className="link" onClick={() => { setMode(mode === "signup" ? "login" : "signup"); setError(""); }}>
            {mode === "signup" ? "Sign in" : "Create an account"}
          </button>
        </p>
      </section>
    </main>
  );
}
