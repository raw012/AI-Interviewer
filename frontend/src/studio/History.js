/** All past interviews with scores; open a report, resume, or delete. */
import React, { useEffect, useState } from "react";
import { IconTrash } from "@tabler/icons-react";
import { api } from "./api";
import { Badge, Empty, READINESS, Spinner, formatDate } from "./ui";

export default function History({ go }) {
  const [items, setItems] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => { api.get("/studio/interviews").then((d) => setItems(d.interviews)).catch((e) => setError(e.message)); }, []);
  async function remove(id) {
    if (!window.confirm("Delete this interview and its feedback? This can't be undone.")) return;
    await api.del(`/studio/interviews/${id}`);
    setItems((list) => list.filter((x) => x.session_id !== id));
  }
  if (error) return <div className="page"><p className="error">{error}</p></div>;
  if (!items) return <div className="page center"><Spinner label="Loading…" /></div>;
  return (
    <div className="page">
      <h1 className="page-title">History</h1>
      {items.length === 0 ? (
        <Empty title="No interviews yet" action={<button className="btn btn-primary" onClick={() => go("/")}>Start one</button>}>Every interview you do is saved here with its transcript and feedback.</Empty>
      ) : (
        <div className="history">
          {items.map((r) => (
            <div key={r.session_id} className="history-row card">
              <button className="history-main" onClick={() => go(r.status === "completed" ? `/report/${r.session_id}` : `/room/${r.session_id}`)}>
                <span className="history-score">{r.status === "completed" ? Number(r.overall_score || 0).toFixed(1) : "–"}</span>
                <span>
                  <strong>{r.title}</strong>
                  <span className="muted small">{formatDate(r.created_at)} · {r.duration_minutes} min · {r.exchanges} answers</span>
                  {r.headline && <span className="small">{r.headline}</span>}
                </span>
                {r.status === "completed" ? <Badge tone={READINESS[r.verdict]?.tone || "cool"}>{READINESS[r.verdict]?.label || "Completed"}</Badge> : <Badge tone="warm">In progress</Badge>}
              </button>
              <button className="icon-btn" aria-label="Delete interview" onClick={() => remove(r.session_id)}><IconTrash size={16} /></button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
