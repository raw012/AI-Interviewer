import React, { useEffect, useRef, useState } from "react";
import AppNavigation from "./AppNavigation";
import PracticePlant from "./PracticePlant";
import { IconKey, IconMicrophone } from "@tabler/icons-react";
import "./App.css";

const API_URL = process.env.REACT_APP_API_URL ||
  (process.env.NODE_ENV === "development" ? "http://localhost:8000" : window.location.origin);

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
  const [resumeStatus, setResumeStatus] = useState({ has_resume: false });
  const [resumeBusy, setResumeBusy] = useState(false);
  const [dashboardData, setDashboardData] = useState({ skills: [], profile: { dimensions: [], has_demo_data: false }, memories: [], interviews: [], recording_reviews: [], summary: {} });
  const [customTopic, setCustomTopic] = useState({ name: "", description: "" });
  const [topicBusy, setTopicBusy] = useState(false);
  const [providerConfig, setProviderConfig] = useState({ providers: [], llm_provider: "groq", transcription_provider: "groq" });
  const [providerConfigLoaded, setProviderConfigLoaded] = useState(false);
  const [providerInputs, setProviderInputs] = useState({});
  const [providerBusy, setProviderBusy] = useState("");
  const [providerMessages, setProviderMessages] = useState({});
  const [durationMinutes, setDurationMinutes] = useState(30);
  const [preferencesRestoredFor, setPreferencesRestoredFor] = useState("");
  const [historyAnswers, setHistoryAnswers] = useState({});
  const [historyInterviews, setHistoryInterviews] = useState(null);
  const [historyLoading, setHistoryLoading] = useState("");
  const [showTranscript, setShowTranscript] = useState(false);
  const [interviewError, setInterviewError] = useState("");

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

  const activeLlm = providerConfig.providers.find((item) => item.key === providerConfig.llm_provider);
  const activeTranscription = providerConfig.providers.find((item) => item.key === providerConfig.transcription_provider);
  const isConnected = (provider) => Boolean(provider?.configured || provider?.server_fallback_available);
  const providersReady = providerConfigLoaded && isConnected(activeLlm) && isConnected(activeTranscription);
  const hasInterviewSource = mode === "special" || resumeStatus.has_resume || Boolean(jobDescription.trim());

  useEffect(() => {
    if (!user?.id) return;
    try {
      const saved = JSON.parse(localStorage.getItem(`interview_prefs:${user.id}`) || "{}");
      if (saved.mode === "general" || saved.mode === "special") setMode(saved.mode);
      if (saved.topic) setTopic(saved.topic);
      if (saved.durationMinutes === 30 || saved.durationMinutes === 60) setDurationMinutes(saved.durationMinutes);
      if (typeof saved.jobDescription === "string") setJobDescription(saved.jobDescription);
    } catch (error) {
      console.warn("Could not read interview preferences", error);
    }
    setPreferencesRestoredFor(user.id);
  }, [user?.id]);

  useEffect(() => {
    if (!user?.id || preferencesRestoredFor !== user.id) return;
    localStorage.setItem(`interview_prefs:${user.id}`, JSON.stringify({ mode, topic, durationMinutes, jobDescription }));
  }, [user?.id, preferencesRestoredFor, mode, topic, durationMinutes, jobDescription]);

  const rememberSession = (data) => {
    localStorage.setItem("interviewer_token", data.token);
    setToken(data.token);
    setUser(data.user);
  };

  const signOut = () => {
    localStorage.removeItem("interviewer_token");
    setToken("");
    setUser(null);
    setProviderConfigLoaded(false);
    setProviderConfig({ providers: [], llm_provider: "groq", transcription_provider: "groq" });
    setPreferencesRestoredFor("");
    setHistoryAnswers({});
    setHistoryInterviews(null);
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
    if (!token || page !== "history") return;
    apiRequest("/history", token)
      .then((response) => response.json())
      .then((data) => setHistoryInterviews(data.interviews || []))
      .catch((error) => setInterviewError(`Could not load past interviews: ${error.message}`));
  }, [token, page]);

  useEffect(() => {
    if (!token) return;
    Promise.all([
      apiRequest("/topics", token).then((response) => response.json()),
      apiRequest("/resume/status", token).then((response) => response.json()),
      apiRequest("/dashboard", token).then((response) => response.json()),
    ])
      .then(([topicData, resumeData, dashboard]) => {
        setTopics(topicData.topics || []);
        setResumeStatus(resumeData);
        setDashboardData(dashboard);
      })
      .catch((error) => console.error("Setup data error:", error));
    apiRequest("/settings/providers", token)
      .then((response) => response.json())
      .then((providers) => setProviderConfig(providers))
      .catch((error) => setInterviewError(`Could not load API settings: ${error.message}`))
      .finally(() => setProviderConfigLoaded(true));
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

  const saveProviderKey = async (provider) => {
    setProviderBusy(provider);
    setProviderMessages((current) => ({ ...current, [provider]: "" }));
    try {
      await apiRequest(`/settings/providers/${provider}/key`, token, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ api_key: providerInputs[provider] || "" }),
      });
      const refreshed = await apiRequest("/settings/providers", token);
      setProviderConfig(await refreshed.json());
      setProviderInputs((current) => ({ ...current, [provider]: "" }));
      setProviderMessages((current) => ({ ...current, [provider]: "API key saved securely." }));
    } catch (error) {
      setProviderMessages((current) => ({ ...current, [provider]: error.message }));
    } finally {
      setProviderBusy("");
    }
  };

  const testProviderKey = async (provider) => {
    setProviderBusy(provider);
    setProviderMessages((current) => ({ ...current, [provider]: "" }));
    try {
      const response = await apiRequest(`/settings/providers/${provider}/test`, token, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ api_key: providerInputs[provider] || "" }),
      });
      const result = await response.json();
      setProviderMessages((current) => ({ ...current, [provider]: result.message }));
    } catch (error) {
      setProviderMessages((current) => ({ ...current, [provider]: error.message }));
    } finally {
      setProviderBusy("");
    }
  };

  const removeProviderKey = async (provider) => {
    if (!window.confirm("Remove this saved API key?")) return;
    setProviderBusy(provider);
    try {
      await apiRequest(`/settings/providers/${provider}/key`, token, { method: "DELETE" });
      const response = await apiRequest("/settings/providers", token);
      setProviderConfig(await response.json());
      setProviderInputs((current) => ({ ...current, [provider]: "" }));
      setProviderMessages((current) => ({ ...current, [provider]: "Saved API key removed." }));
    } catch (error) {
      setProviderMessages((current) => ({ ...current, [provider]: error.message }));
    } finally {
      setProviderBusy("");
    }
  };

  const setActiveProviders = async (field, value) => {
    const next = { ...providerConfig, [field]: value };
    setProviderConfig(next);
    try {
      await apiRequest("/settings/providers/active", token, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ llm_provider: next.llm_provider, transcription_provider: next.transcription_provider }),
      });
    } catch (error) {
      alert(error.message);
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

  const loadHistoryAnswers = async (sessionId) => {
    if (historyAnswers[sessionId] || historyLoading) return;
    setHistoryLoading(sessionId);
    try {
      const response = await apiRequest(`/history/${sessionId}/answers`, token);
      const data = await response.json();
      setHistoryAnswers((current) => ({ ...current, [sessionId]: data.answers || [] }));
    } catch (error) {
      setInterviewError(error.message);
    } finally {
      setHistoryLoading("");
    }
  };

  // ================= CAMERA SETUP =================
  useEffect(() => {
    if (!token || !["question", "recording"].includes(page)) return undefined;
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
    if (!providersReady) {
      setInterviewError("Connect an interview intelligence provider and a transcription provider before starting.");
      setPage("api-settings");
      return;
    }
    if (mode === "general" && !jobDescription.trim() && !resumeStatus.has_resume) {
      alert("Add a job description or upload your resume first.");
      return;
    }
    try {
      setInterviewError("");
      setIsProcessing(true);
      if (!streamRef.current?.getTracks().some((track) => track.readyState === "live")) {
        streamRef.current = await navigator.mediaDevices.getUserMedia({
          video: { width: { ideal: 1280 }, height: { ideal: 720 } },
          audio: true,
        });
      }
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
        setInterviewError(err.message);
        if (err.message.includes("API key") || err.message.includes("provider")) {
          setPage("api-settings");
        }
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
      <div className="app-shell settings-page">
        <AppNavigation page={page} setPage={setPage} signOut={signOut} user={user} />
        <main className="app-main"><div className="settings-container">
          <header><p className="dashboard-eyebrow">ONE-TIME SETUP</p><h1>API settings</h1><p>Connect one provider for interview questions and feedback, and one for audio transcription. Groq or OpenAI can serve both roles with a single key.</p></header>
          {interviewError && <p className="inline-error" role="alert">{interviewError}</p>}
          <section className="settings-card provider-routing">
            <div className="card-heading"><div><h2>Active providers</h2><p>Choose one provider for interview intelligence and one for speech-to-text.</p></div></div>
            <div className="provider-selects">
              <label>Interview intelligence<select value={providerConfig.llm_provider} onChange={(event) => setActiveProviders("llm_provider", event.target.value)}>{providerConfig.providers.filter((item) => item.chat).map((item) => <option key={item.key} value={item.key}>{item.name} · {item.model}</option>)}</select></label>
              <label>Audio transcription<select value={providerConfig.transcription_provider} onChange={(event) => setActiveProviders("transcription_provider", event.target.value)}>{providerConfig.providers.filter((item) => item.transcription).map((item) => <option key={item.key} value={item.key}>{item.name}</option>)}</select></label>
            </div>
          </section>
          <div className="key-security-note"><strong>Your keys stay private.</strong><p>Each key is encrypted before database storage. Complete keys are never returned to the browser. Audio transcription currently supports Groq and OpenAI.</p></div>
          <div className="provider-grid">
            {providerConfig.providers.map((provider) => {
              const connected = provider.configured || provider.server_fallback_available;
              const message = providerMessages[provider.key] || "";
              return (
                <section className="settings-card provider-card" key={provider.key}>
                  <div className="provider-heading"><div className={`provider-logo ${provider.key}`}>{provider.name.charAt(0)}</div><div><h2>{provider.name}</h2><p>{provider.chat ? `Interview model: ${provider.model}` : ""}{provider.transcription ? " · Speech-to-text" : ""}</p></div><span className={connected ? "connected" : "missing"}>{provider.configured ? "Personal key saved" : provider.server_fallback_available ? "Server fallback" : "Not configured"}</span></div>
                  {provider.configured && <div className="saved-key"><span>Saved key</span><code>{provider.masked}</code><small>{provider.updated_at ? new Date(provider.updated_at).toLocaleDateString() : ""}</small></div>}
                  <div className="key-form">
                    <label>{provider.configured ? "Replace API key" : "API key"}<input type="password" autoComplete="off" value={providerInputs[provider.key] || ""} onChange={(event) => setProviderInputs((current) => ({ ...current, [provider.key]: event.target.value }))} placeholder="Paste provider key" /></label>
                    <div className="key-actions"><button type="button" className="btn-secondary" onClick={() => testProviderKey(provider.key)} disabled={providerBusy === provider.key || (!providerInputs[provider.key] && !connected)}>Test</button><button type="button" className="btn-primary" onClick={() => saveProviderKey(provider.key)} disabled={providerBusy === provider.key || !providerInputs[provider.key]}>{providerBusy === provider.key ? "Please wait…" : "Save"}</button>{provider.configured && <button type="button" className="btn-danger-text" onClick={() => removeProviderKey(provider.key)} disabled={providerBusy === provider.key}>Remove</button>}</div>
                  </div>
                  {message && <div className={`key-message${message.toLowerCase().includes("successful") || message.toLowerCase().includes("saved") ? " success" : ""}`}>{message}</div>}
                </section>
              );
            })}
          </div>
        </div></main>
      </div>
    );
  }

  if (["dashboard", "resume", "history"].includes(page)) {
    const completedCount = dashboardData.summary.interviews || 0;
    const completedInterviews = dashboardData.interviews.filter((item) => item.status === "completed");
    const latest = completedInterviews[0];
    const nextMode = mode === "special" ? topics.find((item) => item.key === topic)?.name || "Specialized training" : "General interview";
    return (
      <div className="app-shell">
        <AppNavigation page={page} setPage={setPage} signOut={signOut} user={user} />
        <main className={`app-main${page === "dashboard" && !providersReady ? " needs-provider" : ""}`}>
          <div className="app-main-top"><span>{user.name || user.email}</span><button type="button" onClick={signOut}>Sign out</button></div>
          {page === "dashboard" && <>
            <section className="practice-hero">
              <div className="practice-hero-copy">
                <p className="dashboard-eyebrow">YOUR PRACTICE SPACE</p>
                <h1>Ready for your next<br />mock interview?</h1>
                <p>Practice with realistic questions and build confidence, one answer at a time.</p>
                <div className="quick-settings"><span>{nextMode}</span><span>{durationMinutes} min</span><span>{resumeStatus.has_resume ? "Saved resume" : mode === "special" ? "Focused topic" : "No resume"}</span><button type="button" onClick={() => setPage("setup")}>Change settings</button></div>
              </div>
              <div className="practice-hero-plant"><PracticePlant completed={completedCount} /><strong>Your practice grows</strong><span>{completedCount} completed interview{completedCount === 1 ? "" : "s"}</span></div>
            </section>
            {!providersReady && providerConfigLoaded && <section className="connect-guide" aria-labelledby="connect-guide-heading">
              <div className="connect-guide-heading"><p className="dashboard-eyebrow">ONE-TIME SETUP</p><h2 id="connect-guide-heading">Connect your AI providers</h2><p>Both services need to be ready before your first interview.</p></div>
              <div className="connect-guide-requirements">
                <div><span className="connect-guide-icon"><IconKey size={26} stroke={1.8} aria-hidden="true" /></span><span><strong>Interview intelligence</strong><small>Creates questions and personalized feedback.</small></span><b className={isConnected(activeLlm) ? "is-ready" : ""}>{isConnected(activeLlm) ? "Ready" : "Connect"}</b></div>
                <div><span className="connect-guide-icon"><IconMicrophone size={26} stroke={1.8} aria-hidden="true" /></span><span><strong>Audio transcription</strong><small>Turns your answers into text for review.</small></span><b className={isConnected(activeTranscription) ? "is-ready" : ""}>{isConnected(activeTranscription) ? "Ready" : "Connect"}</b></div>
              </div>
              <button className="btn-primary" onClick={() => setPage("api-settings")}>Connect providers</button>
            </section>}
            <button className="btn-primary quick-start" onClick={hasInterviewSource ? startInterview : () => setPage("setup")} disabled={!providersReady || isProcessing || !providerConfigLoaded}>{isProcessing ? "Preparing interview…" : !providersReady ? "Start interview" : hasInterviewSource ? "Start interview" : "Choose an interview focus"}</button>
            {!hasInterviewSource && providersReady && <p className="quick-start-note">Add a resume, paste a job description, or choose a specialized topic once to enable one-click start.</p>}
            <section className="recent-section"><div className="recent-heading"><h2>Your recent interviews</h2><button type="button" onClick={() => setPage("history")}>View all</button></div>{latest ? <article className="recent-interview"><div><strong>{latest.mode === "special" ? topics.find((item) => item.key === latest.topic)?.name || "Specialized training" : "General interview"}</strong><span>{new Date(latest.created_at).toLocaleDateString()} · {latest.questions_answered} answers</span></div><p>{latest.cumulative_summary || "A step forward in your practice."}</p><button type="button" onClick={() => setPage("history")}>Read feedback</button></article> : <p className="quiet-empty">Your first completed interview will appear here, along with a short feedback summary.</p>}</section>
          </>}
          {page === "resume" && <section className="simple-page"><p className="dashboard-eyebrow">YOUR MATERIALS</p><h1>Resume</h1><p>Upload a PDF once. We will use it for future general interviews until you replace it.</p><div className="simple-panel"><div><strong>{resumeStatus.has_resume ? resumeStatus.filename : "No resume saved yet"}</strong><p>{resumeStatus.has_resume ? "This is your default resume for general interviews." : "A saved resume makes future interviews faster to start."}</p></div><label className="resume-upload">{resumeBusy ? "Processing…" : resumeStatus.has_resume ? "Replace PDF" : "Upload PDF"}<input type="file" accept="application/pdf,.pdf" onChange={uploadResume} disabled={resumeBusy} /></label></div></section>}
          {page === "history" && <section className="simple-page"><p className="dashboard-eyebrow">YOUR PROGRESS</p><h1>Past interviews</h1><p>Review each interview, its feedback summary, and your answers.</p>{interviewError && <p className="inline-error" role="alert">{interviewError}</p>}<div className="past-interviews">{(historyInterviews || []).map((interview) => <details key={interview.session_id} onToggle={(event) => { if (event.currentTarget.open) loadHistoryAnswers(interview.session_id); }}><summary><span><strong>{interview.mode === "special" ? topics.find((item) => item.key === interview.topic)?.name || "Specialized training" : "General interview"}</strong><small>{new Date(interview.created_at).toLocaleString()} · {interview.questions_answered} answers · {interview.duration_minutes} min</small></span><b>{interview.overall_score == null ? "In progress" : `${interview.overall_score}%`}</b></summary><div className="past-detail"><h3>Feedback summary</h3><p>{interview.cumulative_summary || "No feedback summary was generated."}</p>{historyLoading === interview.session_id && <p>Loading answers…</p>}{(historyAnswers[interview.session_id] || []).map((answer) => <div className="past-answer" key={answer.question_number}><strong>{answer.question_number}. {answer.question}</strong><p><b>Your answer:</b> {answer.answer}</p><p><b>What went well:</b> {answer.strengths || "No note"}</p><p><b>Improve next time:</b> {answer.improvements || "No note"}</p><small>Score {answer.score}/100 · {answer.relevance === "mismatch" ? "Marked as mismatched" : "Question fit not flagged"}</small></div>)}</div></details>)}{historyInterviews === null && <p className="quiet-empty">Loading past interviews…</p>}{historyInterviews?.length === 0 && <p className="quiet-empty">No interviews yet. Your first practice session will appear here.</p>}</div></section>}
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
            <h1 className="hero-title">Choose your interview focus</h1>
            <p className="hero-sub">Choose it once. We will remember your settings for next time.</p>
          </div>
          <div className="setup-card">
            <div className="setup-form">
              <div className="mode-switch">
                <button className={mode === "general" ? "active" : ""} onClick={() => setMode("general")}>General</button>
                <button className={mode === "special" ? "active" : ""} onClick={() => setMode("special")}>Specialized</button>
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
              ) : (
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
              )}

              {mode === "general" && <div className="resume-card">
                <div>
                  <strong>Default PDF resume</strong>
                  <p>{resumeStatus.has_resume ? `Currently using: ${resumeStatus.filename}` : "No resume saved. Upload once and reuse it across interviews."}</p>
                </div>
                <label className="resume-upload">
                  {resumeBusy ? "Processing…" : resumeStatus.has_resume ? "Replace" : "Upload PDF"}
                  <input type="file" accept="application/pdf,.pdf" onChange={uploadResume} disabled={resumeBusy} />
                </label>
              </div>}
              <div className="form-group">
                <label className="form-label">Interview duration</label>
                <select className="form-select" value={durationMinutes} onChange={(e) => setDurationMinutes(parseInt(e.target.value))}>
                  <option value={30}>30 minutes</option>
                  <option value={60}>60 minutes</option>
                </select>
              </div>
              <button
                className={`btn-primary${isProcessing ? " btn-loading" : ""}`}
                onClick={startInterview}
                disabled={isProcessing || !providersReady}
              >
                {isProcessing ? <><span className="spinner" /> Preparing…</> : mode === "special" ? "Start specialized training →" : "Start interview →"}
              </button>
              {!providersReady && <p className="inline-error">Connect your AI providers in API settings before starting.</p>}
            </div>
          </div>
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
              <button className="btn-stop" onClick={() => stopRecording(false)} disabled={!recording || isProcessing}>
                <span className="stop-icon" /> Stop My Answer
              </button>
              <button className="btn-finish" onClick={() => stopRecording(true)} disabled={!recording || isProcessing}>
                Finish After This Answer
              </button>
            </div>
            {interviewError && <p className="inline-error" role="alert">{interviewError} You can exit this interview safely.</p>}
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
              <div className="rec-dot-wrap"><span className="rec-dot" /> REC</div>
            </div>
            <div className="transcript-control"><span>Your camera — only you can see this</span><button type="button" onClick={() => setShowTranscript((current) => !current)} aria-expanded={showTranscript}>{showTranscript ? "Hide live transcript" : "Show live transcript"}</button></div>
            {showTranscript && <div className="transcript-panel" aria-live="polite">{liveTranscript || "Your words will appear here while you speak."}</div>}
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
          <div className="result-celebration"><PracticePlant completed={(dashboardData.summary.interviews || 0) + 1} celebrate /><div><p className="dashboard-eyebrow">A NEW LEAF</p><h1 className="results-title">You showed up and grew.</h1><p>Each finished interview adds another leaf to your practice plant.</p></div></div>
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
            <button className="btn-primary" onClick={() => { setPage("dashboard"); setSummaryData(null); setInterviewEndsAt(null); setInterviewTimeLeft(durationMinutes * 60); setInterviewTimeExpired(false); }}>Back to home</button>
          </div>
        </div>
      </div>
    );
  }

  return null;
}

export default App;
