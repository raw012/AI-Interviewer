import React, { useEffect, useRef, useState } from "react";
import "./App.css";

const API_URL = "http://localhost:8000";

async function apiRequest(path, token, options = {}) {
  const headers = new Headers(options.headers || {});
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const response = await fetch(`${API_URL}${path}`, { ...options, headers });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail || payload.error || `Request failed: ${response.status}`);
  }
  return response;
}

function RadarChart({ skills }) {
  const size = 340;
  const center = size / 2;
  const radius = 112;
  const axes = skills.length >= 3 ? skills : [
    { name: "Java OOP", score: 0 },
    { name: "Networks", score: 0 },
    { name: "Operating Systems", score: 0 },
    { name: "Machine Learning", score: 0 },
    { name: "Data Structures", score: 0 },
    { name: "Deep Learning", score: 0 },
  ];
  const point = (index, value = 100) => {
    const angle = -Math.PI / 2 + (index * Math.PI * 2) / axes.length;
    const distance = radius * (value / 100);
    return [center + Math.cos(angle) * distance, center + Math.sin(angle) * distance];
  };
  const polygon = (value) => axes.map((_, index) => point(index, value).join(",")).join(" ");
  const values = axes.map((skill, index) => point(index, skill.score || 0).join(",")).join(" ");
  return (
    <svg className="radar-chart" viewBox={`0 0 ${size} ${size}`} role="img" aria-label="Skill profile radar chart">
      {[25, 50, 75, 100].map((level) => <polygon key={level} points={polygon(level)} className="radar-grid" />)}
      {axes.map((_, index) => {
        const [x, y] = point(index);
        return <line key={index} x1={center} y1={center} x2={x} y2={y} className="radar-axis" />;
      })}
      <polygon points={values} className="radar-value" />
      {axes.map((skill, index) => {
        const [x, y] = point(index, 126);
        return <text key={skill.name} x={x} y={y} className="radar-label" textAnchor={x < center - 8 ? "end" : x > center + 8 ? "start" : "middle"}>{skill.name.length > 17 ? `${skill.name.slice(0, 16)}…` : skill.name}</text>;
      })}
    </svg>
  );
}

function App() {
  const [token, setToken] = useState(() => localStorage.getItem("interviewer_token") || "");
  const [user, setUser] = useState(null);
  const [authMode, setAuthMode] = useState("login");
  const [authForm, setAuthForm] = useState({ email: "", password: "", name: "" });
  const [authError, setAuthError] = useState("");
  const [authBusy, setAuthBusy] = useState(false);
  const [page, setPage] = useState("dashboard");
  const videoRef = useRef(null);
  const mediaRecorderRef = useRef(null);
  const streamRef = useRef(null);
  const recognitionRef = useRef(null);
  const startRecordingRef = useRef(null);
  const finishAfterAnswerRef = useRef(false);
  const discardRecordingRef = useRef(false);

  const [jobDescription, setJobDescription] = useState("");
  const [mode, setMode] = useState("general");
  const [topic, setTopic] = useState("java_oop");
  const [topics, setTopics] = useState([]);
  const [memoryItems, setMemoryItems] = useState([]);
  const [resumeStatus, setResumeStatus] = useState({ has_resume: false });
  const [resumeBusy, setResumeBusy] = useState(false);
  const [recordingFile, setRecordingFile] = useState(null);
  const [reviewBusy, setReviewBusy] = useState(false);
  const [dashboardData, setDashboardData] = useState({ skills: [], memories: [], interviews: [], summary: {} });
  const [customTopic, setCustomTopic] = useState({ name: "", description: "" });
  const [topicBusy, setTopicBusy] = useState(false);
  const [keyStatus, setKeyStatus] = useState({ configured: false, masked: "", server_fallback_available: false });
  const [keyInput, setKeyInput] = useState("");
  const [keyBusy, setKeyBusy] = useState(false);
  const [keyMessage, setKeyMessage] = useState("");
  const [durationMinutes, setDurationMinutes] = useState(30);

  const [recording, setRecording] = useState(false);
  const [question, setQuestion] = useState("");
  const [sessionId, setSessionId] = useState(null);
  const [timeLeft, setTimeLeft] = useState(120);
  const [questionNum, setQuestionNum] = useState(1);
  const [countdown, setCountdown] = useState(5);
  const [isProcessing, setIsProcessing] = useState(false);
  const [liveTranscript, setLiveTranscript] = useState("");
  const [summaryData, setSummaryData] = useState(null);
  const [interviewEndsAt, setInterviewEndsAt] = useState(null);
  const [interviewTimeLeft, setInterviewTimeLeft] = useState(30 * 60);
  const [interviewTimeExpired, setInterviewTimeExpired] = useState(false);

  const formatTime = (seconds) => {
    const safeSeconds = Math.max(0, seconds);
    const minutes = Math.floor(safeSeconds / 60);
    const remainder = safeSeconds % 60;
    return `${minutes}:${String(remainder).padStart(2, "0")}`;
  };

  const rememberSession = (data) => {
    localStorage.setItem("interviewer_token", data.token);
    setToken(data.token);
    setUser(data.user);
  };

  const signOut = () => {
    localStorage.removeItem("interviewer_token");
    setToken("");
    setUser(null);
    setPage("dashboard");
  };

  const submitAuth = async (event) => {
    event.preventDefault();
    setAuthBusy(true);
    setAuthError("");
    try {
      const response = await apiRequest(`/auth/${authMode}`, "", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(authForm),
      });
      rememberSession(await response.json());
    } catch (error) {
      setAuthError(error.message);
    } finally {
      setAuthBusy(false);
    }
  };

  useEffect(() => {
    if (!token) return;
    apiRequest("/auth/me", token)
      .then((response) => response.json())
      .then(setUser)
      .catch(signOut);
  }, [token]);

  useEffect(() => {
    if (!token || page !== "dashboard") return;
    apiRequest("/dashboard", token)
      .then((response) => response.json())
      .then(setDashboardData)
      .catch((error) => console.error("Dashboard refresh error:", error));
  }, [token, page]);

  useEffect(() => {
    if (!token) return;
    Promise.all([
      apiRequest("/topics", token).then((response) => response.json()),
      apiRequest("/resume/status", token).then((response) => response.json()),
      apiRequest("/memory", token).then((response) => response.json()),
      apiRequest("/dashboard", token).then((response) => response.json()),
      apiRequest("/settings/api-key", token).then((response) => response.json()),
    ])
      .then(([topicData, resumeData, memoryData, dashboard, apiKeyData]) => {
        setTopics(topicData.topics || []);
        setResumeStatus(resumeData);
        setMemoryItems(memoryData.items || []);
        setDashboardData(dashboard);
        setKeyStatus(apiKeyData);
      })
      .catch((error) => console.error("Setup data error:", error));
  }, [token]);

  const addCustomTopic = async (event) => {
    event.preventDefault();
    setTopicBusy(true);
    try {
      const response = await apiRequest("/topics", token, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(customTopic),
      });
      const created = await response.json();
      setTopics((current) => [...current, created]);
      setTopic(created.key);
      setCustomTopic({ name: "", description: "" });
    } catch (error) {
      alert(error.message);
    } finally {
      setTopicBusy(false);
    }
  };

  const saveApiKey = async (event) => {
    event.preventDefault();
    setKeyBusy(true);
    setKeyMessage("");
    try {
      const response = await apiRequest("/settings/api-key", token, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ api_key: keyInput }),
      });
      setKeyStatus(await response.json());
      setKeyInput("");
      setKeyMessage("API key saved securely.");
    } catch (error) {
      setKeyMessage(error.message);
    } finally {
      setKeyBusy(false);
    }
  };

  const testApiKey = async () => {
    setKeyBusy(true);
    setKeyMessage("");
    try {
      const response = await apiRequest("/settings/api-key/test", token, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ api_key: keyInput }),
      });
      setKeyMessage((await response.json()).message);
    } catch (error) {
      setKeyMessage(error.message);
    } finally {
      setKeyBusy(false);
    }
  };

  const removeApiKey = async () => {
    if (!window.confirm("Remove your saved Groq API key?")) return;
    setKeyBusy(true);
    try {
      await apiRequest("/settings/api-key", token, { method: "DELETE" });
      const response = await apiRequest("/settings/api-key", token);
      setKeyStatus(await response.json());
      setKeyInput("");
      setKeyMessage("Saved API key removed.");
    } catch (error) {
      setKeyMessage(error.message);
    } finally {
      setKeyBusy(false);
    }
  };

  const uploadResume = async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    setResumeBusy(true);
    try {
      const formData = new FormData();
      formData.append("file", file);
      const response = await apiRequest("/resume", token, { method: "POST", body: formData });
      const data = await response.json();
      setResumeStatus({ has_resume: true, filename: data.filename });
    } catch (error) {
      alert(error.message);
    } finally {
      setResumeBusy(false);
      event.target.value = "";
    }
  };

  const reviewRecording = async () => {
    if (!recordingFile) {
      alert("Please choose an interview audio or video file first.");
      return;
    }
    setReviewBusy(true);
    try {
      const formData = new FormData();
      formData.append("file", recordingFile);
      const response = await apiRequest("/recording-review", token, {
        method: "POST",
        body: formData,
      });
      const data = await response.json();
      setSessionId(data.session_id);
      setSummaryData(data);
      setPage("results");
      const memoryResponse = await apiRequest("/memory", token);
      setMemoryItems((await memoryResponse.json()).items || []);
    } catch (error) {
      alert(error.message);
    } finally {
      setReviewBusy(false);
    }
  };

  // ================= CAMERA SETUP =================
  useEffect(() => {
    if (!token || !["setup", "question", "recording"].includes(page)) return undefined;
    if (streamRef.current?.getTracks().some((track) => track.readyState === "live")) {
      if (videoRef.current) videoRef.current.srcObject = streamRef.current;
      return undefined;
    }
    async function setupCamera() {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: { width: { ideal: 1280 }, height: { ideal: 720 } },
          audio: true,
        });
        streamRef.current = stream;
        if (videoRef.current) videoRef.current.srcObject = stream;
      } catch (err) {
        console.error("Camera error:", err);
        alert("Failed to access camera. Please check permissions.");
      }
    }
    setupCamera();
  }, [token, page]);

  useEffect(() => () => {
    if (streamRef.current) streamRef.current.getTracks().forEach((track) => track.stop());
  }, [token]);

  useEffect(() => {
    if (videoRef.current && streamRef.current && page !== "results") {
      videoRef.current.srcObject = streamRef.current;
    }
  }, [page]);

  // ================= START INTERVIEW =================
  const startInterview = async () => {
    if (mode === "general" && !jobDescription.trim() && !resumeStatus.has_resume) {
      alert("Add a job description or upload your resume first.");
      return;
    }
    try {
      setIsProcessing(true);
      const res = await apiRequest("/start", token, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          job_description: jobDescription,
          duration_minutes: durationMinutes,
          mode,
          topic: mode === "special" ? topic : "",
        }),
      });
      const data = await res.json();
      setSessionId(data.session_id);
      setQuestion(data.question);
      setQuestionNum(data.question_number);
      setInterviewTimeLeft(data.remaining_seconds);
      setInterviewEndsAt(Date.now() + data.remaining_seconds * 1000);
      setInterviewTimeExpired(false);
      setTimeLeft(120);
      setCountdown(5);
      setLiveTranscript("");
      setPage("question");
    } catch (err) {
      alert(`Error: ${err.message}`);
    } finally {
      setIsProcessing(false);
    }
  };

  // ================= RECORDING =================
  const startRecording = () => {
    if (!streamRef.current) { alert("Camera not ready"); return; }

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (SpeechRecognition) {
      const recognition = new SpeechRecognition();
      recognition.continuous = true;
      recognition.interimResults = true;
      recognition.lang = "en-US";
      recognition.onresult = (event) => {
        let finalText = "";
        let interimText = "";
        for (let i = event.resultIndex; i < event.results.length; i++) {
          const t = event.results[i][0].transcript;
          if (event.results[i].isFinal) finalText += t + " ";
          else interimText += t;
        }
        setLiveTranscript((prev) => prev + finalText || interimText);
      };
      recognition.start();
      recognitionRef.current = recognition;
    }

    const recorder = new MediaRecorder(streamRef.current);
    mediaRecorderRef.current = recorder;
    let chunks = [];
    recorder.ondataavailable = (e) => chunks.push(e.data);
    recorder.onstop = async () => {
      if (discardRecordingRef.current) {
        discardRecordingRef.current = false;
        chunks = [];
        setIsProcessing(false);
        return;
      }
      try {
        setIsProcessing(true);
        const blob = new Blob(chunks, { type: "video/webm" });
        const formData = new FormData();
        formData.append("file", blob);
        const shouldFinish = finishAfterAnswerRef.current;
        finishAfterAnswerRef.current = false;
        const res = await apiRequest(`/upload/${sessionId}?finish=${shouldFinish}`, token, { method: "POST", body: formData });
        const data = await res.json();
        if (data.interview_complete) {
          const summaryRes = await apiRequest(`/summary/${sessionId}`, token);
          const summary = await summaryRes.json();
          setSummaryData(summary);
          setPage("results");
        } else {
          setQuestion(data.next_question);
          setQuestionNum(data.question_number);
          if (typeof data.remaining_seconds === "number") {
            setInterviewTimeLeft(data.remaining_seconds);
            setInterviewEndsAt(Date.now() + data.remaining_seconds * 1000);
          }
          setTimeLeft(120);
          setCountdown(5);
          setLiveTranscript("");
          setPage("question");
        }
      } catch (err) {
        alert(`Error: ${err.message}`);
      } finally {
        setIsProcessing(false);
      }
    };
    recorder.start();
    setRecording(true);
    setTimeLeft(120);
  };

  const stopRecording = (finishInterview = false) => {
    finishAfterAnswerRef.current = finishInterview;
    if (mediaRecorderRef.current?.state === "recording") mediaRecorderRef.current.stop();
    if (recognitionRef.current) { recognitionRef.current.stop(); recognitionRef.current = null; }
    setRecording(false);
    setLiveTranscript("");
  };

  const exitInterview = async () => {
    if (!window.confirm("Exit this interview? The current unanswered question will not be saved.")) return;
    discardRecordingRef.current = true;
    finishAfterAnswerRef.current = false;
    if (recognitionRef.current) {
      recognitionRef.current.stop();
      recognitionRef.current = null;
    }
    if (mediaRecorderRef.current?.state === "recording") mediaRecorderRef.current.stop();
    setRecording(false);
    setIsProcessing(false);
    if (sessionId) {
      try {
        await apiRequest(`/cancel/${sessionId}`, token, { method: "POST" });
      } catch (error) {
        console.error("Unable to cancel interview on the server:", error);
      }
    }
    setSessionId(null);
    setInterviewEndsAt(null);
    setInterviewTimeExpired(false);
    setLiveTranscript("");
    setPage("dashboard");
  };

  startRecordingRef.current = startRecording;

  // ================= TIMERS =================
  useEffect(() => {
    if (page !== "question") return;
    setCountdown(5);
    const timer = setInterval(() => {
      setCountdown((prev) => {
        if (prev <= 1) { clearInterval(timer); setPage("recording"); startRecordingRef.current?.(); return 5; }
        return prev - 1;
      });
    }, 1000);
    return () => clearInterval(timer);
  }, [page]);

  useEffect(() => {
    if (!recording || isProcessing) return;
    const timer = setInterval(() => {
      setTimeLeft((prev) => { if (prev <= 1) { stopRecording(); return 120; } return prev - 1; });
    }, 1000);
    return () => clearInterval(timer);
  }, [recording, isProcessing]);

  // The overall interview clock never interrupts the current answer. Once it
  // reaches zero, the backend ends the interview after that answer is uploaded.
  useEffect(() => {
    if (!interviewEndsAt || page === "setup" || page === "results") return;

    const updateInterviewClock = () => {
      const remaining = Math.max(0, Math.ceil((interviewEndsAt - Date.now()) / 1000));
      setInterviewTimeLeft(remaining);
      if (remaining === 0) setInterviewTimeExpired(true);
    };

    updateInterviewClock();
    const timer = setInterval(updateInterviewClock, 1000);
    return () => clearInterval(timer);
  }, [interviewEndsAt, page]);

  const sendQuestionFeedback = async (questionNumber, relevance, issueType) => {
    try {
      await apiRequest(`/feedback/${sessionId}/${questionNumber}`, token, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ relevance, issue_type: issueType }),
      });
      setSummaryData((current) => ({
        ...current,
        interview_history: current.interview_history.map((item) =>
          item.question_number === questionNumber
            ? { ...item, relevance, issue_type: issueType }
            : item
        ),
      }));
    } catch (error) {
      alert(error.message);
    }
  };

  // ================= PAGES =================

  if (!token || !user) {
    const isRegister = authMode === "register";
    return (
      <div className="auth-page">
        <div className="auth-glow" />
        <div className="auth-shell">
          <div className="auth-brand">
            <div className="logo-icon">AI</div>
            <div>
              <div className="logo-text">Interview Coach</div>
              <p>Turn every interview into durable progress.</p>
            </div>
          </div>
          <div className="auth-card">
            <h1>{isRegister ? "Create your account" : "Welcome back"}</h1>
            <p>{isRegister ? "Build a long-term profile from every interview." : "Sign in to continue your interview training."}</p>
            <form onSubmit={submitAuth}>
              {isRegister && (
                <label>
                  Name
                  <input
                    type="text"
                    autoComplete="name"
                    placeholder="How should we address you? (optional)"
                    value={authForm.name}
                    onChange={(event) => setAuthForm({ ...authForm, name: event.target.value })}
                  />
                </label>
              )}
              <label>
                Email
                <input
                  type="email"
                  autoComplete="username"
                  placeholder="your@email.com"
                  value={authForm.email}
                  onChange={(event) => setAuthForm({ ...authForm, email: event.target.value })}
                  required
                />
              </label>
              <label>
                Password
                <input
                  type="password"
                  autoComplete={isRegister ? "new-password" : "current-password"}
                  placeholder={isRegister ? "At least 6 characters" : "Enter your password"}
                  value={authForm.password}
                  onChange={(event) => setAuthForm({ ...authForm, password: event.target.value })}
                  required
                />
              </label>
              {authError && <div className="auth-error">{authError}</div>}
              <button className="btn-primary" type="submit" disabled={authBusy}>
                {authBusy ? "Please wait…" : isRegister ? "Create account" : "Sign in"}
              </button>
            </form>
            <div className="auth-switch">
              {isRegister ? "Already have an account?" : "New to Interview Coach?"}
              <button
                type="button"
                onClick={() => {
                  setAuthMode(isRegister ? "login" : "register");
                  setAuthError("");
                }}
              >
                {isRegister ? "Sign in" : "Create an account"}
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (page === "api-settings") {
    return (
      <div className="page-bg settings-page">
        <nav className="navbar">
          <div className="navbar-logo"><div className="logo-icon">AI</div><span className="logo-text">Interview Coach</span></div>
          <div className="user-menu"><button onClick={() => setPage("dashboard")}>Dashboard</button><button onClick={signOut}>Sign out</button></div>
        </nav>
        <main className="settings-container">
          <header><p className="dashboard-eyebrow">SETTINGS</p><h1>API settings</h1><p>Connect your own AI provider key for interviews, scoring, transcription, and recording review.</p></header>
          <section className="settings-card">
            <div className="provider-heading"><div className="provider-logo">G</div><div><h2>Groq</h2><p>Used for Llama interview intelligence and Whisper transcription.</p></div><span className={keyStatus.configured || keyStatus.server_fallback_available ? "connected" : "missing"}>{keyStatus.configured ? "Personal key saved" : keyStatus.server_fallback_available ? "Using server fallback" : "Not configured"}</span></div>
            <div className="key-security-note"><strong>Your key stays private.</strong><p>It is encrypted before being stored in the local database. The complete key is never returned to the browser or shown again.</p></div>
            {keyStatus.configured && <div className="saved-key"><span>Saved key</span><code>{keyStatus.masked}</code><small>Updated {new Date(keyStatus.updated_at).toLocaleString()}</small></div>}
            <form className="key-form" onSubmit={saveApiKey}>
              <label>{keyStatus.configured ? "Replace API key" : "Groq API key"}<input type="password" autoComplete="off" value={keyInput} onChange={(event) => setKeyInput(event.target.value)} placeholder="gsk_…" required /></label>
              <p>Get a key from the Groq Console. It should begin with <code>gsk_</code>.</p>
              <div className="key-actions"><button type="button" className="btn-secondary" onClick={testApiKey} disabled={keyBusy || (!keyInput && !keyStatus.configured && !keyStatus.server_fallback_available)}>Test connection</button><button type="submit" className="btn-primary" disabled={keyBusy || !keyInput}>{keyBusy ? "Please wait…" : "Save key"}</button>{keyStatus.configured && <button type="button" className="btn-danger-text" onClick={removeApiKey} disabled={keyBusy}>Remove saved key</button>}</div>
            </form>
            {keyMessage && <div className={`key-message${keyMessage.toLowerCase().includes("successful") || keyMessage.toLowerCase().includes("saved") ? " success" : ""}`}>{keyMessage}</div>}
          </section>
        </main>
      </div>
    );
  }

  if (page === "dashboard") {
    const skillScores = new Map(dashboardData.skills.map((skill) => [skill.topic, skill]));
    const radarSkills = topics.slice(0, 10).map((item) => ({
      name: item.name,
      score: Number(skillScores.get(item.key)?.score || 0),
    }));
    return (
      <div className="page-bg dashboard-page">
        <nav className="navbar">
          <div className="navbar-logo"><div className="logo-icon">AI</div><span className="logo-text">Interview Coach</span></div>
          <div className="user-menu"><span>{user.name || user.email}</span><button onClick={() => setPage("api-settings")}>API settings</button><button onClick={signOut}>Sign out</button></div>
        </nav>
        <main className="dashboard-container">
          <header className="dashboard-hero">
            <div><p className="dashboard-eyebrow">YOUR INTERVIEW PROFILE</p><h1>Welcome back, {user.name || user.email.split("@")[0]}</h1><p>Review what the coach remembers, track your skill profile, and choose what to practice next.</p></div>
            <button className="btn-primary dashboard-start" onClick={() => setPage("setup")}>Start an interview →</button>
          </header>
          <section className="metric-grid">
            <article><strong>{dashboardData.summary.interviews || 0}</strong><span>Interviews</span></article>
            <article><strong>{dashboardData.summary.active_memories || 0}</strong><span>Active memories</span></article>
            <article><strong>{dashboardData.summary.strong_points || 0}</strong><span>Demonstrated strengths</span></article>
            <article><strong>{dashboardData.summary.weak_points || 0}</strong><span>Areas to revisit</span></article>
          </section>
          <section className="dashboard-grid">
            <article className="dashboard-card radar-card">
              <div className="card-heading"><div><h2>Skill profile</h2><p>Scores are based on relevant, reviewed answers.</p></div></div>
              <RadarChart skills={radarSkills} />
              {dashboardData.skills.length === 0 && <p className="empty-note">Complete your first interview to begin building this profile.</p>}
            </article>
            <article className="dashboard-card strengths-card">
              <div className="card-heading"><div><h2>Strengths and growth areas</h2><p>Evidence extracted from your answers.</p></div></div>
              <div className="insight-columns">
                <div><h3>Strengths</h3>{dashboardData.memories.filter((item) => item.kind === "strong_point").slice(0, 5).map((item) => <p key={item.id}>✓ {item.content}</p>)}{!dashboardData.memories.some((item) => item.kind === "strong_point") && <span className="empty-note">No verified strengths yet.</span>}</div>
                <div><h3>Needs attention</h3>{dashboardData.memories.filter((item) => item.kind === "weak_point").slice(0, 5).map((item) => <p key={item.id}>↗ {item.content}</p>)}{!dashboardData.memories.some((item) => item.kind === "weak_point") && <span className="empty-note">No verified gaps yet.</span>}</div>
              </div>
            </article>
          </section>
          <section className="dashboard-card memory-browser">
            <div className="card-heading"><div><h2>Coach memory</h2><p>See exactly what is carried into future interviews and where it came from.</p></div><span>{dashboardData.memories.length} active</span></div>
            <div className="memory-list">
              {dashboardData.memories.map((item) => (
                <article className={`memory-row ${item.kind}`} key={item.id}>
                  <span className="memory-kind">{item.kind === "weak_point" ? "Growth area" : "Strength"}</span>
                  <div><strong>{item.content}</strong><p>{item.topic || "General interview"} · seen {item.times_seen} time{item.times_seen === 1 ? "" : "s"} · confidence {Math.round(item.confidence * 100)}%</p>{item.question && <small>Evidence question: {item.question}</small>}</div>
                  <div className="memory-source">{item.interview_date ? new Date(item.interview_date).toLocaleDateString() : "Imported memory"}</div>
                </article>
              ))}
              {dashboardData.memories.length === 0 && <p className="empty-note">The coach has not stored any verified memory yet.</p>}
            </div>
          </section>
          <section className="dashboard-card history-card">
            <div className="card-heading"><div><h2>Interview history and context</h2><p>Open a session to inspect the compact context retained from it.</p></div></div>
            <div className="history-list">
              {dashboardData.interviews.map((interview) => (
                <details key={interview.session_id}>
                  <summary><div><strong>{interview.mode === "special" ? topics.find((item) => item.key === interview.topic)?.name || "Specialized training" : interview.mode === "recording" ? "Recording review" : "General interview"}</strong><span>{new Date(interview.created_at).toLocaleString()} · {interview.questions_answered} answers</span></div><b>{interview.overall_score == null ? "In progress" : `${interview.overall_score}%`}</b></summary>
                  <div className="history-context"><strong>Retained context</strong><p>{interview.cumulative_summary || "No compact context was generated for this session."}</p></div>
                  <div className="history-memories"><strong>Memories from this interview</strong>{dashboardData.memories.filter((item) => item.session_id === interview.session_id).map((item) => <span key={item.id} className={item.kind}>• {item.content}</span>)}{!dashboardData.memories.some((item) => item.session_id === interview.session_id) && <span>No active memory from this interview.</span>}</div>
                </details>
              ))}
              {dashboardData.interviews.length === 0 && <p className="empty-note">No interview history yet.</p>}
            </div>
          </section>
        </main>
      </div>
    );
  }

  // ── SETUP PAGE ──
  if (page === "setup") {
    return (
      <div className="page-bg">
        <nav className="navbar">
          <div className="navbar-logo">
            <div className="logo-icon">AI</div>
            <span className="logo-text">Interview Coach</span>
          </div>
          <div className="user-menu">
            <span>{user.name || user.email}</span>
            <button onClick={() => setPage("dashboard")}>Dashboard</button>
            <button onClick={() => setPage("api-settings")}>API settings</button>
            <button onClick={signOut}>Sign out</button>
          </div>
        </nav>
        <div className="setup-container">
          <div className="hero">
            <button className="back-dashboard" onClick={() => setPage("dashboard")}>← Back to dashboard</button>
            <h1 className="hero-title">Ace your technical interview</h1>
            <p className="hero-sub">AI-powered practice tailored to your job description. Get real-time feedback.</p>
          </div>
          <div className="setup-card">
            <div className="camera-preview-wrap">
              <video ref={videoRef} autoPlay muted className="camera-preview-video" />
              <div className="camera-badge">📹 Camera Preview</div>
            </div>
            <div className="setup-form">
              <div className="mode-switch">
                <button className={mode === "general" ? "active" : ""} onClick={() => setMode("general")}>General</button>
                <button className={mode === "special" ? "active" : ""} onClick={() => setMode("special")}>Specialized</button>
                <button className={mode === "review" ? "active" : ""} onClick={() => setMode("review")}>Recording review</button>
              </div>

              {mode === "general" ? (
                <div className="form-group">
                  <label className="form-label">Job description <span className="optional">(optional when a resume is saved)</span></label>
                  <textarea
                    className="form-textarea"
                    placeholder="Paste a job description to keep the interview in scope…"
                    value={jobDescription}
                    onChange={(e) => setJobDescription(e.target.value)}
                  />
                </div>
              ) : mode === "special" ? (
                <div className="form-group">
                  <label className="form-label">Training topic</label>
                  <select className="form-select" value={topic} onChange={(e) => setTopic(e.target.value)}>
                    {topics.map((item) => (
                      <option key={item.key} value={item.key}>{item.name}</option>
                    ))}
                  </select>
                  <p className="form-help">{topics.find((item) => item.key === topic)?.description}</p>
                  <details className="custom-topic-box">
                    <summary>+ Add your own topic</summary>
                    <form onSubmit={addCustomTopic}>
                      <input required maxLength={60} placeholder="Topic name" value={customTopic.name} onChange={(event) => setCustomTopic({ ...customTopic, name: event.target.value })} />
                      <textarea maxLength={300} placeholder="What should the interviewer cover?" value={customTopic.description} onChange={(event) => setCustomTopic({ ...customTopic, description: event.target.value })} />
                      <button type="submit" disabled={topicBusy}>{topicBusy ? "Adding…" : "Add topic"}</button>
                    </form>
                  </details>
                </div>
              ) : (
                <div className="recording-upload-card">
                  <strong>Upload a real interview recording</strong>
                  <p>Supports MP3, WAV, M4A, WebM, MP4, and MOV up to 200 MB. The coach identifies Q&A pairs and creates a detailed retrospective.</p>
                  <label className="recording-upload">
                    {recordingFile ? recordingFile.name : "Choose audio or video"}
                    <input
                      type="file"
                      accept="audio/*,video/*,.webm,.m4a"
                      onChange={(event) => setRecordingFile(event.target.files?.[0] || null)}
                    />
                  </label>
                </div>
              )}

              {mode !== "review" && <div className="resume-card">
                <div>
                  <strong>Default PDF resume</strong>
                  <p>{resumeStatus.has_resume ? `Currently using: ${resumeStatus.filename}` : "No resume saved. Upload once and reuse it across interviews."}</p>
                </div>
                <label className="resume-upload">
                  {resumeBusy ? "Processing…" : resumeStatus.has_resume ? "Replace" : "Upload PDF"}
                  <input type="file" accept="application/pdf,.pdf" onChange={uploadResume} disabled={resumeBusy} />
                </label>
              </div>}
              {mode !== "review" && <div className="form-group">
                <label className="form-label">Interview duration</label>
                <select className="form-select" value={durationMinutes} onChange={(e) => setDurationMinutes(parseInt(e.target.value))}>
                  <option value={30}>30 minutes</option>
                  <option value={60}>60 minutes</option>
                </select>
              </div>}
              <button
                className={`btn-primary${isProcessing || reviewBusy ? " btn-loading" : ""}`}
                onClick={mode === "review" ? reviewRecording : startInterview}
                disabled={isProcessing || reviewBusy}
              >
                {reviewBusy ? <><span className="spinner" /> Transcribing and analyzing…</> : isProcessing ? <><span className="spinner" /> Preparing…</> : mode === "review" ? "Review recording →" : mode === "special" ? "Start specialized training →" : "Start interview →"}
              </button>
            </div>
          </div>
          {memoryItems.length > 0 && (
            <section className="memory-panel">
              <div className="memory-heading">
                <div><h2>Learning memory</h2><p>Future interviews revisit relevant growth areas without repeating the same questions.</p></div>
                <span>{memoryItems.length} items</span>
              </div>
              <div className="memory-grid">
                {memoryItems.slice(0, 6).map((item) => (
                  <article className={`memory-card ${item.kind}`} key={item.id}>
                    <div><span>{item.kind === "weak_point" ? "Needs attention" : "Strength"}</span><small>{item.topic || "General"}</small></div>
                    <p>{item.content}</p>
                    <footer>Seen {item.times_seen} time{item.times_seen === 1 ? "" : "s"} · {Math.round(item.confidence * 100)}% confidence</footer>
                  </article>
                ))}
              </div>
            </section>
          )}
        </div>
      </div>
    );
  }

  // ── QUESTION PREVIEW PAGE ──
  if (page === "question") {
    const circumference = 2 * Math.PI * 36;
    const pct = countdown / 5;
    return (
      <div className="fullpage-center page-bg">
        <nav className="navbar">
          <div className="navbar-logo">
            <div className="logo-icon">AI</div>
            <span className="logo-text">Interview Coach</span>
          </div>
          <div className="navbar-status">
            <div className="progress-pill">Question {questionNum}</div>
            <div className={`progress-pill${interviewTimeExpired ? " time-expired" : ""}`}>{formatTime(interviewTimeLeft)}</div>
            <button className="exit-interview" onClick={exitInterview}>Exit interview</button>
          </div>
        </nav>
        <div className="question-preview-card">
          <p className="q-eyebrow">Read the question carefully</p>
          <h2 className="q-text">{question}</h2>
          <div className="countdown-ring-wrap">
            <svg className="countdown-ring" viewBox="0 0 80 80">
              <circle cx="40" cy="40" r="36" className="ring-bg" />
              <circle
                cx="40" cy="40" r="36"
                className="ring-fill"
                strokeDasharray={circumference}
                strokeDashoffset={circumference * (1 - pct)}
              />
            </svg>
            <div className="countdown-num">{countdown}</div>
          </div>
          <p className="countdown-hint">Recording starts automatically in {countdown} second{countdown !== 1 ? "s" : ""}</p>
          {interviewTimeExpired && <p className="time-expired-note">Time is up. Complete this final answer to receive your feedback.</p>}
        </div>
      </div>
    );
  }

  // ── RECORDING PAGE ──
  if (page === "recording") {
    const timerPct = (timeLeft / 120) * 100;
    const isLow = timeLeft <= 30;
    return (
      <div className="recording-page page-bg">
        <nav className="navbar">
          <div className="navbar-logo">
            <div className="logo-icon">AI</div>
            <span className="logo-text">Interview Coach</span>
          </div>
          <div className="navbar-status">
            <div className="progress-pill">Question {questionNum}</div>
            <div className={`progress-pill${interviewTimeExpired ? " time-expired" : ""}`}>{formatTime(interviewTimeLeft)}</div>
            <button className="exit-interview" onClick={exitInterview}>Exit interview</button>
          </div>
        </nav>
        <div className="recording-body">
          {/* Left panel */}
          <div className="recording-left">
            <div className="q-card">
              <span className="q-card-label">Current Question</span>
              <p className="q-card-text">{question}</p>
            </div>
            <div className="timer-section">
              <div className="timer-row">
                <span className="timer-label">Time remaining</span>
                <span className={`timer-value${isLow ? " timer-low" : ""}`}>{timeLeft}s</span>
              </div>
              <div className="timer-bar-bg">
                <div className={`timer-bar-fill${isLow ? " timer-bar-low" : ""}`} style={{ width: `${timerPct}%` }} />
              </div>
            </div>
            {interviewTimeExpired && (
              <div className="time-expired-banner">
                Interview time is up. Your current answer will still be scored, then the interview will end.
              </div>
            )}
            <div className="recording-btns">
              <button className="btn-stop" onClick={() => stopRecording(false)}>
                <span className="stop-icon" /> Stop My Answer
              </button>
              <button className="btn-finish" onClick={() => stopRecording(true)}>
                Finish After This Answer
              </button>
            </div>
            {isProcessing && (
              <div className="processing-banner">
                <span className="spinner spinner-dark" /> Analyzing your answer...
              </div>
            )}
          </div>
          {/* Right panel: camera */}
          <div className="recording-right">
            <div className="video-frame">
              <video ref={videoRef} autoPlay muted className="recording-video" />
              {liveTranscript && <div className="subtitle">{liveTranscript}</div>}
              <div className="rec-dot-wrap"><span className="rec-dot" /> REC</div>
            </div>
            <p className="video-hint">Your camera — only you can see this</p>
          </div>
        </div>
      </div>
    );
  }

  // ── RESULTS PAGE ──
  if (page === "results" && summaryData) {
    return (
      <div className="page-bg results-bg">
        <nav className="navbar">
          <div className="navbar-logo">
            <div className="logo-icon">AI</div>
            <span className="logo-text">Interview Coach</span>
          </div>
        </nav>
        <div className="results-container">
          <h1 className="results-title">Interview Complete 🎉</h1>
          <p className="results-meta">{summaryData.mode === "recording" ? "Real interview recording review" : `${summaryData.duration_minutes}-minute interview`} · {summaryData.questions_answered} answers completed</p>
          <div className="score-row">
            <div className="score-card">
              <div className="score-num">{summaryData.overall_score}%</div>
              <div className="score-lbl">Overall Score</div>
            </div>
          </div>
          {summaryData.encouraging_message && (
            <div className="encouragement">{summaryData.encouraging_message}</div>
          )}
          {summaryData.summary && <div className="review-summary"><strong>Overall retrospective</strong><p>{summaryData.summary}</p></div>}
          <h2 className="section-title">Question Breakdown</h2>
          <div className="results-table-wrap">
            <table className="results-table">
              <thead>
                <tr>
                  <th>#</th><th>Question</th><th>Your Answer</th>
                  <th>Improvements</th><th>Score</th><th>Question fit</th>
                </tr>
              </thead>
              <tbody>
                {summaryData.interview_history.map((item, idx) => (
                  <tr key={idx}>
                    <td>{item.question_number}</td>
                    <td><div className="cell-scroll">{item.question}</div></td>
                    <td><div className="cell-scroll">{item.transcript}</div></td>
                    <td><div className="cell-scroll cell-small">{item.improvements}</div></td>
                    <td>
                      <span className={`score-badge ${item.score >= 75 ? "score-good" : item.score >= 60 ? "score-mid" : "score-low-badge"}`}>
                        {item.score}
                      </span>
                    </td>
                    <td>
                      {item.relevance === "pending" ? (
                        <div className="feedback-actions">
                          <button onClick={() => sendQuestionFeedback(item.question_number, "expected", "")}>Relevant</button>
                          <button onClick={() => sendQuestionFeedback(item.question_number, "expected", "knowledge_gap")}>I did not know this</button>
                          <button className="feedback-mismatch" onClick={() => sendQuestionFeedback(item.question_number, "mismatch", "question_mismatch")}>Question was mismatched</button>
                        </div>
                      ) : (
                        <span className={`feedback-status ${item.relevance}`}>
                          {item.relevance === "mismatch" ? "Marked mismatched" : item.issue_type === "knowledge_gap" ? "Knowledge gap" : "Relevant"}
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="results-actions">
            <button className="btn-primary" onClick={() => { setPage("dashboard"); setJobDescription(""); setDurationMinutes(30); setSummaryData(null); setInterviewEndsAt(null); setInterviewTimeLeft(30 * 60); setInterviewTimeExpired(false); }}>Back to dashboard</button>
          </div>
        </div>
      </div>
    );
  }

  return null;
}

export default App;
