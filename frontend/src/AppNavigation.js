import React from "react";
import { IconHome2, IconFileCv, IconHistory, IconKey } from "@tabler/icons-react";

const ITEMS = [
  { page: "dashboard", label: "Home", Icon: IconHome2 },
  { page: "resume", label: "Resume", Icon: IconFileCv },
  { page: "history", label: "Past interviews", Icon: IconHistory },
  { page: "api-settings", label: "API settings", Icon: IconKey },
];

export default function AppNavigation({ page, setPage, signOut, user }) {
  const links = ITEMS.map(({ page: destination, label, Icon }) => (
    <button
      type="button"
      className={`app-nav-link${page === destination ? " is-active" : ""}`}
      aria-current={page === destination ? "page" : undefined}
      onClick={() => setPage(destination)}
      key={destination}
    >
      <Icon size={21} stroke={1.9} aria-hidden="true" />
      <span>{label}</span>
    </button>
  ));

  return (
    <>
      <aside className="app-sidebar" aria-label="Main navigation">
        <div className="app-sidebar-brand"><span className="logo-icon">AI</span><strong>Interview Coach</strong></div>
        <nav>{links}</nav>
        <div className="app-sidebar-account"><span>{user?.name || user?.email}</span><button type="button" onClick={signOut}>Sign out</button></div>
      </aside>
      <nav className="mobile-tabs" aria-label="Main navigation">{links}</nav>
    </>
  );
}
