/** What the interviewer remembers: grouped, editable, deletable, with the policy in plain words. */
import React, { useEffect, useState } from "react";
import { IconPencil, IconTrash, IconCheck } from "@tabler/icons-react";
import { api } from "./api";
import { Badge, Empty, Spinner } from "./ui";

const GROUPS = [
  { kind: "growth", title: "Skills to work on", note: "Brought back on a schedule (1, 3, 7, 14, 30 days) until you've shown it consistently." },
  { kind: "strength", title: "Strengths", note: "Helps the interviewer spend less time on what you already do well." },
  { kind: "story", title: "Stories you've told", note: "So you aren't asked for the same story twice, and follow-ups can go deeper." },
  { kind: "fact", title: "Background", note: "Career context you shared." },
  { kind: "preference", title: "Preferences", note: "How you like to practise." },
];
const STATUS = { candidate: ["Noticed once", "cool"], active: ["Active", "warm"], resolved: ["Improved", "good"] };

function Item({ item, onChange, onDelete, competencies }) {
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(item.content);
  const [label, tone] = STATUS[item.status] || STATUS.active;
  async function save() {
    await api.patch(`/studio/memory/${item.id}`, { content: text });
    onChange({ ...item, content: text });
    setEditing(false);
  }
  return (
    <li className="mem-item">
      <div className="mem-main">
        {editing ? (
          <div className="row"><input value={text} onChange={(e) => setText(e.target.value)} maxLength={220} /><button className="icon-btn" onClick={save} aria-label="Save"><IconCheck size={16} /></button></div>
        ) : (
          <p>{item.content}</p>
        )}
        <div className="row wrap small muted">
          {item.topic && <span>{competencies[item.topic] || item.topic}</span>}
          {item.kind === "growth" && <Badge tone={tone}>{label}</Badge>}
          {item.times_seen > 1 && <span>seen {item.times_seen}×</span>}
          {item.evidence && <span title={item.evidence}>“{item.evidence.slice(0, 60)}{item.evidence.length > 60 ? "…" : ""}”</span>}
        </div>
      </div>
      <div className="row">
        <button className="icon-btn" aria-label="Edit" onClick={() => setEditing(!editing)}><IconPencil size={15} /></button>
        <button className="icon-btn" aria-label="Forget" onClick={() => onDelete(item.id)}><IconTrash size={15} /></button>
      </div>
    </li>
  );
}

export default function Memory({ config, profile, refreshProfile }) {
  const [items, setItems] = useState(null);
  const [note, setNote] = useState({ kind: "fact", content: "" });
  const [error, setError] = useState("");
  const enabled = profile?.prefs?.memory_enabled !== false;
  useEffect(() => { api.get("/studio/memory").then((d) => setItems(d.items)).catch((e) => setError(e.message)); }, []);

  async function remove(id) {
    await api.del(`/studio/memory/${id}`);
    setItems((list) => list.filter((x) => x.id !== id));
  }
  async function add(e) {
    e.preventDefault();
    setError("");
    try {
      await api.post("/studio/memory", note);
      setNote({ ...note, content: "" });
      setItems((await api.get("/studio/memory")).items);
    } catch (err) { setError(err.message); }
  }
  async function clearAll() {
    if (!window.confirm("Forget everything the interviewer has learned about you? Interview history is kept.")) return;
    await api.del("/studio/memory");
    setItems([]);
  }
  async function toggle() {
    await api.put("/studio/profile", { prefs: { memory_enabled: !enabled } });
    refreshProfile();
  }

  return (
    <div className="page memory">
      <h1 className="page-title">What I remember</h1>
      <div className="card policy">
        <div>
          <h3>How memory works</h3>
          <p>I keep short notes that make your next interview more useful: skills to revisit, strengths, stories you've used and context you've shared. I don't keep recordings, and I never store health, family, age, ethnicity, religion, politics, immigration or salary details. A one-off slip is only noted once and fades unless it happens again.</p>
        </div>
        <label className="switch">
          <input type="checkbox" checked={enabled} onChange={toggle} />
          <span>{enabled ? "Memory on" : "Memory off"}</span>
        </label>
      </div>
      {error && <p className="error">{error}</p>}
      {!items ? <Spinner label="Loading…" /> : items.length === 0 ? (
        <Empty title="Nothing yet">After your first interview, you'll see what I noted here. You can edit or delete anything.</Empty>
      ) : (
        <div className="mem-groups">
          {GROUPS.map((g) => {
            const list = items.filter((x) => x.kind === g.kind);
            if (!list.length) return null;
            return (
              <section key={g.kind} className="card">
                <h3>{g.title}</h3>
                <p className="small muted">{g.note}</p>
                <ul className="mem-list">
                  {list.map((item) => <Item key={item.id} item={item} competencies={config.competencies} onDelete={remove} onChange={(next) => setItems((all) => all.map((x) => (x.id === next.id ? next : x)))} />)}
                </ul>
              </section>
            );
          })}
        </div>
      )}
      <form className="card add-note" onSubmit={add}>
        <h3>Tell me something to remember</h3>
        <div className="row">
          <select value={note.kind} onChange={(e) => setNote({ ...note, kind: e.target.value })}>
            <option value="fact">Background</option>
            <option value="preference">Preference</option>
            <option value="growth">Something to work on</option>
          </select>
          <input value={note.content} onChange={(e) => setNote({ ...note, content: e.target.value })} placeholder="e.g. I'm switching from mechanical engineering to software" maxLength={220} />
          <button className="btn btn-soft" disabled={note.content.trim().length < 12}>Save</button>
        </div>
      </form>
      {items?.length > 0 && <button className="link danger" onClick={clearAll}>Forget everything</button>}
    </div>
  );
}
