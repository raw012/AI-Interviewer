import React, { useEffect, useRef, useState } from "react";
import "./App.css";

function App() {
  const [page, setPage] = useState("setup");
  const videoRef = useRef(null);
  const mediaRecorderRef = useRef(null);
  const streamRef = useRef(null);
  const recognitionRef = useRef(null);
  const startRecordingRef = useRef(null);
  const finishAfterAnswerRef = useRef(false);

  const [jobDescription, setJobDescription] = useState("");
  const [resume, setResume] = useState("");
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

  // ================= CAMERA SETUP =================
  useEffect(() => {
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
    return () => {
      if (streamRef.current) streamRef.current.getTracks().forEach(t => t.stop());
    };
  }, []);

  useEffect(() => {
    if (videoRef.current && streamRef.current && page !== "results") {
      videoRef.current.srcObject = streamRef.current;
    }
  }, [page]);

  // ================= START INTERVIEW =================
  const startInterview = async () => {
    if (!jobDescription.trim()) { alert("Please paste a job description"); return; }
    try {
      setIsProcessing(true);
      const res = await fetch("http://localhost:8000/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ job_description: jobDescription, resume, duration_minutes: durationMinutes }),
      });
      if (!res.ok) throw new Error(`Server error: ${res.status}`);
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
      try {
        setIsProcessing(true);
        const blob = new Blob(chunks, { type: "video/webm" });
        const formData = new FormData();
        formData.append("file", blob);
        const shouldFinish = finishAfterAnswerRef.current;
        finishAfterAnswerRef.current = false;
        const res = await fetch(`http://localhost:8000/upload/${sessionId}?finish=${shouldFinish}`, { method: "POST", body: formData });
        if (!res.ok) {
          const errorData = await res.json().catch(() => ({}));
          throw new Error(errorData.error || `Upload failed: ${res.status}`);
        }
        const data = await res.json();
        if (data.interview_complete) {
          const summaryRes = await fetch(`http://localhost:8000/summary/${sessionId}`);
          if (!summaryRes.ok) throw new Error("Failed to fetch summary");
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

  // ================= PAGES =================

  // ── SETUP PAGE ──
  if (page === "setup") {
    return (
      <div className="page-bg">
        <nav className="navbar">
          <div className="navbar-logo">
            <div className="logo-icon">AI</div>
            <span className="logo-text">Interview Coach</span>
          </div>
        </nav>
        <div className="setup-container">
          <div className="hero">
            <h1 className="hero-title">Ace your technical interview</h1>
            <p className="hero-sub">AI-powered practice tailored to your job description. Get real-time feedback.</p>
          </div>
          <div className="setup-card">
            <div className="camera-preview-wrap">
              <video ref={videoRef} autoPlay muted className="camera-preview-video" />
              <div className="camera-badge">📹 Camera Preview</div>
            </div>
            <div className="setup-form">
              <div className="form-group">
                <label className="form-label">Job Description <span className="required">*</span></label>
                <textarea
                  className="form-textarea"
                  placeholder="Paste the full job description here..."
                  value={jobDescription}
                  onChange={(e) => setJobDescription(e.target.value)}
                />
              </div>
              <div className="form-group">
                <label className="form-label">Resume <span className="optional">(Optional)</span></label>
                <textarea
                  className="form-textarea form-textarea-sm"
                  placeholder="Paste your resume or leave blank..."
                  value={resume}
                  onChange={(e) => setResume(e.target.value)}
                />
              </div>
              <div className="form-group">
                <label className="form-label">Interview Duration</label>
                <select className="form-select" value={durationMinutes} onChange={(e) => setDurationMinutes(parseInt(e.target.value))}>
                  <option value={30}>30 minutes</option>
                  <option value={60}>60 minutes</option>
                </select>
              </div>
              <button className={`btn-primary${isProcessing ? " btn-loading" : ""}`} onClick={startInterview} disabled={isProcessing}>
                {isProcessing ? <><span className="spinner" /> Preparing...</> : "Start Interview →"}
              </button>
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
              <button className="btn-stop" onClick={stopRecording}>
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
          <p className="results-meta">{summaryData.duration_minutes}-minute interview · {summaryData.questions_answered} answers completed</p>
          <div className="score-row">
            <div className="score-card">
              <div className="score-num">{summaryData.overall_score}%</div>
              <div className="score-lbl">Overall Score</div>
            </div>
          </div>
          {summaryData.encouraging_message && (
            <div className="encouragement">{summaryData.encouraging_message}</div>
          )}
          <h2 className="section-title">Question Breakdown</h2>
          <div className="results-table-wrap">
            <table className="results-table">
              <thead>
                <tr>
                  <th>#</th><th>Question</th><th>Your Answer</th>
                  <th>Improvements</th><th>Score</th>
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
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="results-actions">
            <button className="btn-primary" onClick={() => { setPage("setup"); setJobDescription(""); setResume(""); setDurationMinutes(30); setSummaryData(null); setInterviewEndsAt(null); setInterviewTimeLeft(30 * 60); setInterviewTimeExpired(false); }}>
              Practice Again
            </button>
          </div>
        </div>
      </div>
    );
  }

  return null;
}

export default App;
