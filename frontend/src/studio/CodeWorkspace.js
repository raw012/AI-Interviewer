/** Code workspace: problem statement, editor, run, and test results. Runs entirely in the browser. */
import React, { useEffect, useMemo, useRef, useState } from "react";
import { IconCheck, IconPlayerPlayFilled, IconRefresh, IconTestPipe, IconX } from "@tabler/icons-react";
import { LANGUAGES, entryName, preload, runCode, starterCode } from "./runner";
import { Badge, PROVENANCE } from "./ui";

const show = (v) => (typeof v === "string" ? JSON.stringify(v) : JSON.stringify(v));

function callText(harness, test, language) {
  if (harness.kind === "class") return test.args[0].map((op) => `${op[0]}(${op.slice(1).map(show).join(", ")})`).join(" → ");
  return `${entryName(harness, language)}(${test.args.map(show).join(", ")})`;
}

function Editor({ value, onChange, language }) {
  const area = useRef(null);
  const gutter = useRef(null);
  const lines = value.split("\n").length;
  const unit = language === "python" ? "    " : "  ";
  function onKeyDown(e) {
    const el = e.target;
    const { selectionStart: s, selectionEnd: en } = el;
    const set = (next, caret) => { onChange(next); requestAnimationFrame(() => { el.selectionStart = el.selectionEnd = caret; }); };
    if (e.key === "Tab") {
      e.preventDefault();
      set(value.slice(0, s) + unit + value.slice(en), s + unit.length);
    } else if (e.key === "Enter") {
      e.preventDefault();
      const lineStart = value.lastIndexOf("\n", s - 1) + 1;
      const line = value.slice(lineStart, s);
      let indent = line.match(/^\s*/)[0];
      if (/[:{[(]\s*$/.test(line)) indent += unit;
      set(`${value.slice(0, s)}\n${indent}${value.slice(en)}`, s + 1 + indent.length);
    } else if (e.key === "Backspace" && s === en) {
      const lineStart = value.lastIndexOf("\n", s - 1) + 1;
      const before = value.slice(lineStart, s);
      if (before && /^\s+$/.test(before) && before.length % unit.length === 0) {
        e.preventDefault();
        set(value.slice(0, s - unit.length) + value.slice(s), s - unit.length);
      }
    }
  }
  return (
    <div className="editor">
      <pre className="editor-gutter" ref={gutter} aria-hidden="true">{Array.from({ length: lines }, (_, i) => i + 1).join("\n")}</pre>
      <textarea
        ref={area}
        value={value}
        spellCheck={false}
        autoCapitalize="off"
        autoCorrect="off"
        aria-label="Code editor"
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={onKeyDown}
        onScroll={(e) => { if (gutter.current) gutter.current.scrollTop = e.target.scrollTop; }}
      />
    </div>
  );
}

export default function CodeWorkspace({ problem, onChange }) {
  const harness = problem?.harness || null;
  const [language, setLanguage] = useState("python");
  const [codes, setCodes] = useState({});
  const [result, setResult] = useState(null);
  const [status, setStatus] = useState("idle");
  const [tab, setTab] = useState("tests");
  const code = codes[language] ?? starterCode(harness, language);
  const examples = useMemo(() => (harness ? harness.tests.slice(0, 2) : []), [harness]);

  useEffect(() => { preload("python"); }, []);
  useEffect(() => { setCodes({}); setResult(null); }, [problem?.id]);
  useEffect(() => {
    const summary = result?.tests?.length
      ? { language, passed: result.tests.filter((t) => t.pass).length, total: result.tests.length, failing: result.tests.filter((t) => !t.pass).slice(0, 3).map((t) => `${callText(harness, t, language)} expected ${show(t.expected)} got ${t.error ? "error: " + t.error.split("\n").pop() : show(t.got)}`) }
      : { language };
    onChange?.({ code: codes[language] ? code : "", run: summary });
  }, [codes, result, language]); // eslint-disable-line react-hooks/exhaustive-deps

  async function run(tests) {
    setTab(tests ? "tests" : "output");
    const res = await runCode({ language, code, harness, tests, onStatus: setStatus });
    setStatus("idle");
    setResult({ ...res, ranTests: tests });
    if (res.error && !res.tests.length) setTab("output");
  }

  const passed = result?.tests?.filter((t) => t.pass).length || 0;
  const prov = PROVENANCE[problem?.provenance] || PROVENANCE.practice;
  const busy = status !== "idle";
  return (
    <section className="workspace">
      <div className="ws-problem">
        <div className="row wrap">
          <h3>{problem?.title || "Scratchpad"}</h3>
          {problem?.trending ? <Badge tone="warm" title={problem.trending}>Asked recently</Badge> : problem && <Badge tone={prov.tone}>{prov.label}</Badge>}
        </div>
        {problem?.trending && <p className="ws-trend">{problem.trending}</p>}
        <p>{problem?.text}</p>
        {examples.map((t, i) => (
          <pre key={i} className="ws-example">{callText(harness, t, language)}{"\n"}→ {show(t.expected)}</pre>
        ))}
        {harness && <p className="ws-note">Implement <code>{entryName(harness, language)}</code>. {harness.compare !== "exact" && harness.compare !== "float" ? "Output order doesn't matter. " : ""}Talk through your approach before you code, like in a real interview.</p>}
      </div>
      <div className="ws-code">
        <div className="ws-bar">
          <div className="segmented segmented--dark">
            {LANGUAGES.map((l) => <button key={l.key} className={language === l.key ? "is-on" : ""} onClick={() => { setLanguage(l.key); setResult(null); }}>{l.label}</button>)}
          </div>
          <div className="row">
            <button className="tool" title="Reset to starter code" onClick={() => { if (window.confirm("Reset your code to the starter?")) { setCodes({ ...codes, [language]: undefined }); setResult(null); } }}><IconRefresh size={15} /></button>
            <button className="tool" onClick={() => run(false)} disabled={busy}><IconPlayerPlayFilled size={14} /> Run</button>
            {harness && <button className="btn btn-primary btn-sm" onClick={() => run(true)} disabled={busy}><IconTestPipe size={15} /> Run tests</button>}
          </div>
        </div>
        <Editor value={code} language={language} onChange={(next) => setCodes({ ...codes, [language]: next })} />
        <div className="ws-out">
          <div className="ws-tabs">
            {harness && <button className={tab === "tests" ? "is-on" : ""} onClick={() => setTab("tests")}>Tests{result?.tests?.length ? ` ${passed}/${result.tests.length}` : ""}</button>}
            <button className={tab === "output" ? "is-on" : ""} onClick={() => setTab("output")}>Output</button>
            <span className="ws-status">{status === "loading" ? "Loading Python runtime (first run only)…" : status === "running" ? "Running…" : ""}</span>
          </div>
          {tab === "output" || !harness ? (
            <pre className={`ws-console${result?.error ? " has-error" : ""}`}>{result ? [result.stdout, result.error].filter(Boolean).join("\n") || "(no output)" : "Run your code to see printed output and errors here."}</pre>
          ) : !result?.tests?.length ? (
            <pre className={`ws-console${result?.error ? " has-error" : ""}`}>{result?.error || `${harness.tests.length} test cases, including edge cases. Run tests when you're ready.`}</pre>
          ) : (
            <ul className="ws-tests">
              {result.tests.map((t, i) => (
                <li key={i} className={t.pass ? "is-pass" : "is-fail"}>
                  <span className="ws-mark">{t.pass ? <IconCheck size={14} /> : <IconX size={14} />}</span>
                  <div>
                    <code>{callText(harness, t, language)}</code>
                    {!t.pass && <div className="ws-diff">expected <code>{show(t.expected)}</code>{t.error ? <> · error <code>{t.error.split("\n").pop()}</code></> : <> · got <code>{show(t.got)}</code></>}</div>}
                    {t.stdout && <pre className="ws-stdout">{t.stdout}</pre>}
                  </div>
                  <span className="ws-ms">{t.ms} ms</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </section>
  );
}
