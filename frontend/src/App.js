import React, { useEffect, useRef, useState } from "react";
import "./App.css";

function App() {
  const [page, setPage] = useState("setup");
  const videoRef = useRef(null);
  const mediaRecorderRef = useRef(null);
  const streamRef = useRef(null);
  const recognitionRef = useRef(null);

  const [jobDescription, setJobDescription] = useState("");
  const [resume, setResume] = useState("");
  const [numQuestions, setNumQuestions] = useState(5);

  const [recording, setRecording] = useState(false);
  const [question, setQuestion] = useState("");
  const [sessionId, setSessionId] = useState(null);
  const [timeLeft, setTimeLeft] = useState(120);
  const [questionNum, setQuestionNum] = useState(1);
  const [totalQuestions, setTotalQuestions] = useState(5);
  const [countdown, setCountdown] = useState(5);
  const [isProcessing, setIsProcessing] = useState(false);
  const [liveTranscript, setLiveTranscript] = useState("");
  const [summaryData, setSummaryData] = useState(null);
  const [playbackData, setPlaybackData] = useState(null);
  const [currentPlaybackQuestion, setCurrentPlaybackQuestion] = useState(null);
  const [dynamicCountdown, setDynamicCountdown] = useState(5);

  // ================= PLAYBACK =================
  const startPlayback = async (sessionId, questionNumber) => {
    try {
      const res = await fetch(`http://localhost:8000/playback/${sessionId}/${questionNumber}`);
      if (!res.ok) throw new Error("Failed to load playback data");
      const data = await res.json();
      setPlaybackData(data);
      setCurrentPlaybackQuestion(questionNumber);
      setPage("playback");
    } catch (err) {
      alert(`Error loading playback: ${err.message}`);
    }
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

  // ================= TEXT-TO-SPEECH =================
  const speakQuestion = (text) => {
    if ("speechSynthesis" in window) {
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.rate = 0.95;
      utterance.pitch = 1.0;
      utterance.volume = 1.0;
      window.speechSynthesis.speak(utterance);
    }
  };

  // ================= START INTERVIEW =================
  const startInterview = async () => {
    if (!jobDescription.trim()) { alert("Please paste a job description"); return; }
    try {
      setIsProcessing(true);
      const res = await fetch("http://localhost:8000/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ job_description: jobDescription, resume, num_questions: numQuestions }),
      });
      if (!res.ok) throw new Error(`Server error: ${res.status}`);
      const data = await res.json();
      setSessionId(data.session_id);
      setQuestion(data.question);
      setQuestionNum(data.question_number);
      setTotalQuestions(data.total_questions);
      setTimeLeft(120);
      const newCountdown = calculateCountdown(data.question);
      setDynamicCountdown(newCountdown);
      setCountdown(newCountdown);
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
        const res = await fetch(`http://localhost:8000/upload/${sessionId}`, { method: "POST", body: formData });
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
          setTimeLeft(120);
          const newCountdown = calculateCountdown(data.next_question);
          setDynamicCountdown(newCountdown);
          setCountdown(newCountdown);
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

  const stopRecording = () => {
    if (mediaRecorderRef.current) mediaRecorderRef.current.stop();
    if (recognitionRef.current) { recognitionRef.current.stop(); recognitionRef.current = null; }
    setRecording(false);
    setLiveTranscript("");
  };

  // ================= TIMERS =================
  // Calculate dynamic countdown based on question length
  const calculateCountdown = (questionText) => {
    // Formula: max(3, length × 0.05), capped at 15
    if (!questionText) return 5;
    const calculated = Math.max(3, Math.ceil(questionText.length * 0.05));
    return Math.min(calculated, 15);
  };

  useEffect(() => {
    if (page === "question" && question) {
      // Calculate and set the dynamic countdown based on question length
      const newCountdown = calculateCountdown(question);
      setDynamicCountdown(newCountdown);
      setCountdown(newCountdown);
    }
  }, [question, page]);

  useEffect(() => {
    if (page !== "question") return;
    const timer = setInterval(() => {
      setCountdown((prev) => {
        if (prev <= 1) { clearInterval(timer); setPage("recording"); startRecording(); return dynamicCountdown; }
        return prev - 1;
      });
    }, 1000);
    return () => clearInterval(timer);
  }, [page, dynamicCountdown]);

  useEffect(() => {
    if (!recording || isProcessing) return;
    const timer = setInterval(() => {
      setTimeLeft((prev) => { if (prev <= 1) { stopRecording(); return 120; } return prev - 1; });
    }, 1000);
    return () => clearInterval(timer);
  }, [recording, isProcessing]);

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
                <label className="form-label">Number of Questions</label>
                <select className="form-select" value={numQuestions} onChange={(e) => setNumQuestions(parseInt(e.target.value))}>
                  {[3, 4, 5, 6, 7, 8, 9, 10].map((n) => (
                    <option key={n} value={n}>{n} questions (~{n * 3} min)</option>
                  ))}dynamicCountdown;
    return (
      <div className="fullpage-center page-bg">
        <nav className="navbar">
          <div className="navbar-logo">
            <div className="logo-icon">AI</div>
            <span className="logo-text">Interview Coach</span>
          </div>
          <div className="progress-pill">Question {questionNum} of {totalQuestions}</div>
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
          <p className="countdown-tip" style={{fontSize: "12px", color: "#999", marginTop: "12px"}}>Countdown time adapts to question length (3-15 seconds)</p>
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
          <div className="progress-pill">Question {questionNum} of {totalQuestions}</div>
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
            <div className="recording-btns">
              <button className="btn-stop" onClick={stopRecording}>
                <span className="stop-icon" /> Stop My Answer
              </button>
              <button className="btn-finish" onClick={() => setPage("results")}>
                Finish Interview
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
                  <th>Score</th><th>Strengths</th><th>Improvements</th><th>Video</th>
                </tr>
              </thead>
              <tbody>
                {summaryDatbutton className="video-link-btn" onClick={() => startPlayback(sessionId, item.question_number)}>Watch</button
                  <tr key={idx}>
                    <td>{item.question_number}</td>
                    <td><div className="cell-scroll">{item.question}</div></td>
                    <td><div className="cell-scroll">{item.transcript?.substring(0, 120)}...</div></td>
                    <td>
                      <span className={`score-badge ${item.score >= 75 ? "score-good" : item.score >= 60 ? "score-mid" : "score-low-badge"}`}>
                        {item.score}
                      </span>
                    </td>
                    <td><div className="cell-scroll cell-small">{item.strengths}</div></td>
                    <td><div className="cell-scroll cell-small">{item.improvements}</div></td>
                    <td>
                      {item.video_path
                        ? <a href={item.video_path} target="_blank" rel="noopener noreferrer" className="video-link">Watch</a>
                        : <span className="no-video">—</span>}
                    </td>
                  </tr>
  // ── PLAYBACK PAGE ──
  if (page === "playback" && playbackData) {
    return (
      <div className="page-bg">
        <nav className="navbar">
          <div className="navbar-logo">
            <div className="logo-icon">AI</div>
            <span className="logo-text">Interview Coach</span>
          </div>
          <div className="progress-pill">Question {playbackData.question_number}</div>
        </nav>
        <div className="playback-container">
          <div className="playback-video-wrap">
            <video 
              className="playback-video" 
              controls 
              autoPlay
              src={playbackData.video_path}
            />
          </div>
          <div className="playback-info">
            <h2 className="playback-question">{playbackData.question}</h2>
            <div className="playback-score">
              <span className={`score-badge ${playbackData.evaluation.score >= 75 ? "score-good" : playbackData.evaluation.score >= 60 ? "score-mid" : "score-low-badge"}`}>
                Score: {playbackData.evaluation.score}
              </span>
            </div>
            <div className="playback-section">
              <h3>Core Knowledge Points</h3>
              <p>{playbackData.evaluation.key_concepts}</p>
            </div>
            <div className="playback-section">
              <h3>Reference Answer Points</h3>
              <p>{playbackData.evaluation.reference_answer}</p>
            </div>
            <div className="playback-section">
              <h3>Strengths</h3>
              <p>{playbackData.evaluation.strengths}</p>
            </div>
            <div className="playback-section">
              <h3>Areas for Improvement</h3>
              <p>{playbackData.evaluation.improvements}</p>
            </div>
            <div className="playback-section">
              <h3>Improvement Suggestions</h3>
              <p>{playbackData.evaluation.suggestions}</p>
            </div>
            <div className="playback-section">
              <h3>Your Answer</h3>
              <p className="transcript">{playbackData.transcript}</p>
            </div>
            <button className="btn-primary" onClick={() => setPage("results")}>
              Back to Results
            </button>
          </div>
        </div>
      </div>
    );
  }

                ))}
              </tbody>
            </table>
          </div>
          <div className="results-actions">
            <button className="btn-primary" onClick={() => { setPage("setup"); setJobDescription(""); setResume(""); setNumQuestions(5); setSummaryData(null); }}>
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