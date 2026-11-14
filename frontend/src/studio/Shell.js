/** Signed-in shell: hash routing, navigation, onboarding, and shared state. */
import React, { useCallback, useEffect, useState } from "react";
import { IconBrain, IconHistory, IconHome, IconLogout, IconSettings } from "@tabler/icons-react";
import { api, tokenStore } from "./api";
import Auth from "./Auth";
import History from "./History";
import Home from "./Home";
import Intake from "./Intake";
import Memory from "./Memory";
import Onboarding from "./Onboarding";
import Report from "./Report";
import Room from "./Room";
import Settings from "./Settings";
import { Spinner } from "./ui";
import "./studio.css";

function useHashRoute() {
  const read = () => (window.location.hash.replace(/^#/, "") || "/").split("#")[0];
  const [route, setRoute] = useState(read);
  useEffect(() => {
    const on = () => setRoute(read());
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  const go = useCallback((path) => {
    window.location.hash = path;
    window.scrollTo({ top: 0 });
  }, []);
  return [route, go];
}

const NAV = [
  ["/", "Practice", IconHome],
  ["/history", "History", IconHistory],
  ["/memory", "Memory", IconBrain],
  ["/settings", "Settings", IconSettings],
];

export default function Shell() {
  const [route, go] = useHashRoute();
  const [config, setConfig] = useState(null);
  const [user, setUser] = useState(null);
  const [profile, setProfile] = useState(null);
  const [checking, setChecking] = useState(Boolean(tokenStore.get()));
  const [draft, setDraft] = useState(null);
  const [started, setStarted] = useState(null);
  const [tour, setTour] = useState(false);
  const [providerReady, setProviderReady] = useState(true);

  useEffect(() => { api.get("/studio/config").then(setConfig).catch(() => setConfig({ personas: [], rounds: [], roles: [], levels: [], pressures: [], competencies: {} })); }, []);

  const refreshProfile = useCallback(async () => {
    const p = await api.get("/studio/profile");
    setProfile(p);
    setUser(p.user);
    return p;
  }, []);

  const signOut = useCallback(() => {
    if (tokenStore.get()) api.post("/studio/account/sign-out").catch(() => {});
    tokenStore.set("");
    setUser(null);
    setProfile(null);
    go("/");
  }, [go]);

  useEffect(() => {
    if (!tokenStore.get()) return;
    refreshProfile().then((p) => setTour(!p.onboarding_done)).catch(() => tokenStore.set("")).finally(() => setChecking(false));
    const expired = () => { tokenStore.set(""); setUser(null); };
    window.addEventListener("auth-expired", expired);
    return () => window.removeEventListener("auth-expired", expired);
  }, [refreshProfile]);

  useEffect(() => {
    if (!user) return;
    api.get("/settings/providers").then((d) => {
      setProviderReady(d.providers.some((p) => p.chat && (p.configured || p.server_fallback_available)));
    }).catch(() => {});
  }, [user, route]);

  async function signedIn() {
    const p = await refreshProfile();
    setTour(!p.onboarding_done);
  }

  async function closeTour() {
    setTour(false);
    await api.put("/studio/profile", { onboarding_done: true }).catch(() => {});
  }

  if (!config || checking) return <div className="boot"><Spinner label="Loading…" /></div>;
  if (!user) return <Auth config={config} onSignedIn={signedIn} />;

  const [, section, param] = route.split("/");
  const inRoom = section === "room";
  let page;
  if (section === "new") page = <Intake draft={draft} config={config} profile={profile} go={go} onStarted={setStarted} refreshProfile={refreshProfile} />;
  else if (section === "room") page = <Room key={param} sessionId={param} start={started} config={config} profile={profile} user={user} go={go} />;
  else if (section === "report") page = <Report key={param} sessionId={param} config={config} profile={profile} go={go} setDraft={setDraft} />;
  else if (section === "history") page = <History go={go} />;
  else if (section === "memory") page = <Memory config={config} profile={profile} refreshProfile={refreshProfile} />;
  else if (section === "settings") page = <Settings config={config} profile={profile} refreshProfile={refreshProfile} user={user} onSignOut={signOut} replayTour={() => setTour(true)} />;
  else page = <Home user={user} config={config} profile={profile} go={go} setDraft={setDraft} providerReady={providerReady} />;

  return (
    <div className={`app${inRoom ? " app--room" : ""}`}>
      {!inRoom && (
        <nav className="nav">
          <button className="brand" onClick={() => go("/")}><span className="brand-mark">AI</span> Interviewer</button>
          <div className="nav-links">
            {NAV.map(([path, label, Icon]) => (
              <button key={path} className={`nav-link${(path === "/" ? !section || section === "new" : section === path.slice(1)) ? " is-active" : ""}`} onClick={() => go(path)}>
                <Icon size={18} /> <span>{label}</span>
              </button>
            ))}
          </div>
          <button className="nav-link" onClick={signOut} title="Sign out"><IconLogout size={18} /><span className="sr-only">Sign out</span></button>
        </nav>
      )}
      {page}
      {tour && <Onboarding persona={config.personas[0]} onDone={closeTour} />}
    </div>
  );
}
