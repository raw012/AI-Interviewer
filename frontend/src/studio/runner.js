/** Run candidate code in the browser: Python (Pyodide, WebAssembly) and JavaScript, each in a Web Worker.
 *  Nothing is executed on the server. A run that exceeds the time limit is terminated. */

const PYODIDE = "https://cdn.jsdelivr.net/pyodide/v0.26.4/full/pyodide.js";
const TIME_LIMIT_MS = 8000;

const PY_RUNNER = `
import json, sys, io, time, copy, traceback
_h = json.loads(HARNESS_JSON)
_res = {"stdout": "", "error": "", "tests": []}
_buf = io.StringIO()
_old = sys.stdout
sys.stdout = _buf
_ns = {"__name__": "__main__"}

def _tb():
    lines = traceback.format_exc().splitlines()
    keep = [l for l in lines if "<exec>" not in l and "_pyodide" not in l and "pyodide" not in l.lower()]
    return "\\n".join(keep[-8:])

def _norm(v, mode):
    try:
        if mode == "sorted":
            return sorted(v)
        if mode == "groups":
            return sorted(sorted(g) for g in v)
        if mode == "float":
            return round(float(v), 6)
    except Exception:
        return v
    return v

try:
    exec(compile(USER_CODE, "solution.py", "exec"), _ns)
except BaseException:
    _res["error"] = _tb()

if _h and RUN_TESTS and not _res["error"]:
    _name = _h["function"]
    if _name not in _ns:
        _res["error"] = f"Define {'class' if _h['kind'] == 'class' else 'function'} {_name} to run the tests."
    else:
        for _t in _h["tests"]:
            _case = {"args": _t["args"], "expected": _t["expected"], "pass": False, "got": None, "error": ""}
            _mark = _buf.tell()
            _start = time.perf_counter()
            try:
                _args = copy.deepcopy(_t["args"])
                if _h["kind"] == "class":
                    _obj, _out = None, []
                    for _op in _args[0]:
                        if _op[0] == _name:
                            _obj = _ns[_name](*_op[1:]); _out.append(None)
                        else:
                            _out.append(getattr(_obj, _op[0])(*_op[1:]))
                    _got = _out
                else:
                    _got = _ns[_name](*_args)
                _got = json.loads(json.dumps(_got, default=list))
                _case["got"] = _got
                _case["pass"] = _norm(_got, _h["compare"]) == _norm(_t["expected"], _h["compare"])
            except BaseException:
                _case["error"] = _tb()
            _case["ms"] = round((time.perf_counter() - _start) * 1000, 2)
            _case["stdout"] = _buf.getvalue()[_mark:][:2000]
            _res["tests"].append(_case)

sys.stdout = _old
_res["stdout"] = _buf.getvalue()[:20000]
json.dumps(_res, default=str)
`;

const PY_WORKER = `
importScripts(${JSON.stringify(PYODIDE)});
const ready = loadPyodide().then((py) => { postMessage({ type: "ready" }); return py; });
onmessage = async (e) => {
  try {
    const py = await ready;
    py.globals.set("USER_CODE", e.data.code);
    py.globals.set("HARNESS_JSON", JSON.stringify(e.data.harness || null));
    py.globals.set("RUN_TESTS", !!e.data.tests);
    const out = await py.runPythonAsync(${JSON.stringify(PY_RUNNER)});
    postMessage({ type: "result", result: JSON.parse(out) });
  } catch (err) {
    postMessage({ type: "result", result: { stdout: "", error: String(err && err.message || err), tests: [] } });
  }
};
`;

const JS_WORKER = `
postMessage({ type: "ready" });
const fmt = (v) => { if (typeof v === "string") return v; try { return JSON.stringify(v); } catch { return String(v); } };
const norm = (v, mode) => {
  try {
    if (mode === "sorted") return [...v].sort((a, b) => (a > b ? 1 : a < b ? -1 : 0));
    if (mode === "groups") return v.map((g) => [...g].sort((a, b) => (a > b ? 1 : a < b ? -1 : 0))).map((g) => JSON.stringify(g)).sort();
    if (mode === "float") return Math.round(Number(v) * 1e6) / 1e6;
  } catch { return v; }
  return v;
};
onmessage = (e) => {
  const { code, harness, tests, name } = e.data;
  const logs = [];
  const fake = { log: (...a) => logs.push(a.map(fmt).join(" ")), error: (...a) => logs.push(a.map(fmt).join(" ")), warn: (...a) => logs.push(a.map(fmt).join(" ")), info: (...a) => logs.push(a.map(fmt).join(" ")) };
  const res = { stdout: "", error: "", tests: [] };
  let impl;
  try {
    const probe = name ? "; return (typeof " + name + " !== 'undefined') ? " + name + " : undefined;" : "";
    impl = new Function("console", '"use strict";' + code + "\\n" + probe)(fake);
  } catch (err) {
    res.error = (err && err.stack ? String(err.stack).split("\\n").slice(0, 3).join("\\n") : String(err));
  }
  if (harness && tests && !res.error) {
    if (typeof impl !== "function") res.error = "Define " + (harness.kind === "class" ? "class " : "function ") + name + " to run the tests.";
    else for (const t of harness.tests) {
      const c = { args: t.args, expected: t.expected, pass: false, got: null, error: "" };
      const mark = logs.length;
      const start = performance.now();
      try {
        const args = JSON.parse(JSON.stringify(t.args));
        let got;
        if (harness.kind === "class") {
          let obj = null; got = [];
          for (const op of args[0]) {
            if (op[0] === harness.function) { obj = new impl(...op.slice(1)); got.push(null); }
            else { const r = obj[op[0]](...op.slice(1)); got.push(r === undefined ? null : r); }
          }
        } else got = impl(...args);
        got = got === undefined ? null : JSON.parse(JSON.stringify(got));
        c.got = got;
        c.pass = JSON.stringify(norm(got, harness.compare)) === JSON.stringify(norm(t.expected, harness.compare));
      } catch (err) { c.error = String(err && err.message || err); }
      c.ms = Math.round((performance.now() - start) * 100) / 100;
      c.stdout = logs.slice(mark).join("\\n").slice(0, 2000);
      res.tests.push(c);
    }
  }
  res.stdout = logs.join("\\n").slice(0, 20000);
  postMessage({ type: "result", result: res });
};
`;

export const LANGUAGES = [
  { key: "python", label: "Python 3" },
  { key: "javascript", label: "JavaScript" },
];

export function camel(name) {
  return name.replace(/_([a-z])/g, (_, c) => c.toUpperCase());
}

/** The name the candidate must define in the chosen language. */
export function entryName(harness, language) {
  if (!harness) return "";
  return harness.kind === "class" || language === "python" ? harness.function : camel(harness.function);
}

export function starterCode(harness, language) {
  if (!harness) return language === "python" ? "# Write your solution here\n" : "// Write your solution here\n";
  if (harness.kind === "class") {
    const ops = harness.tests[0].args[0];
    const methods = new Map();
    ops.slice(1).forEach((op) => methods.set(op[0], op.length - 1));
    const ctor = ops[0].length - 1;
    const names = (n) => ["a", "b", "c", "d"].slice(0, n);
    if (language === "python") {
      const body = [...methods].map(([m, n]) => `    def ${m}(self${names(n).map((x) => `, ${x}`).join("")}):\n        pass\n`).join("\n");
      return `class ${harness.function}:\n    def __init__(self${ctor ? ", capacity" : ""}):\n        pass\n\n${body}`;
    }
    const body = [...methods].map(([m, n]) => `  ${m}(${names(n).join(", ")}) {\n  }\n`).join("\n");
    return `class ${harness.function} {\n  constructor(${ctor ? "capacity" : ""}) {\n  }\n\n${body}}\n`;
  }
  if (language === "python") return `def ${harness.function}(${harness.params.join(", ")}):\n    # your code here\n    pass\n`;
  return `function ${camel(harness.function)}(${harness.params.map(camel).join(", ")}) {\n  // your code here\n}\n`;
}

const workers = {};

function getWorker(language) {
  if (workers[language]) return workers[language];
  const source = language === "python" ? PY_WORKER : JS_WORKER;
  const worker = new Worker(URL.createObjectURL(new Blob([source], { type: "text/javascript" })));
  const entry = { worker, ready: false, waiters: [] };
  worker.addEventListener("message", (e) => {
    if (e.data.type === "ready") { entry.ready = true; entry.waiters.forEach((fn) => fn()); entry.waiters = []; }
  });
  workers[language] = entry;
  return entry;
}

/** Warm up the Python runtime so the first run is fast. */
export function preload(language) {
  try { getWorker(language); } catch { /* workers unavailable */ }
}

export function runCode({ language, code, harness, tests = false, onStatus = () => {} }) {
  return new Promise((resolve) => {
    let entry;
    try { entry = getWorker(language); } catch (err) {
      resolve({ stdout: "", error: "This browser can't run code in the page.", tests: [] });
      return;
    }
    let timer;
    const finish = (result) => { clearTimeout(timer); entry.worker.removeEventListener("message", onMessage); entry.worker.removeEventListener("error", onError); resolve(result); };
    const onMessage = (e) => { if (e.data.type === "result") finish(e.data.result); };
    const onError = () => { delete workers[language]; finish({ stdout: "", error: language === "python" ? "Couldn't load the Python runtime. Check your connection and try again." : "The code could not be run.", tests: [] }); };
    entry.worker.addEventListener("message", onMessage);
    entry.worker.addEventListener("error", onError);
    const begin = () => {
      onStatus("running");
      timer = setTimeout(() => {
        entry.worker.terminate();
        delete workers[language];
        finish({ stdout: "", error: `Time limit exceeded (${TIME_LIMIT_MS / 1000}s). Check for an infinite loop or an approach that is too slow.`, tests: [], timeout: true });
      }, TIME_LIMIT_MS);
      entry.worker.postMessage({ code, harness, tests, name: entryName(harness, language) });
    };
    if (entry.ready) begin();
    else { onStatus("loading"); entry.waiters.push(begin); }
  });
}
