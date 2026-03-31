import React, { useEffect, useRef, useState } from "react";

function App() {
  const [page, setPage] = useState("setup"); // "setup" | "question" | "recording" | "results"
  const videoRef = useRef(null);
  const mediaRecorderRef = useRef(null);
  const streamRef = useRef(null);
  const recognitionRef = useRef(null);

  // Setup page state
  const [jobDescription, setJobDescription] = useState("");
  const [resume, setResume] = useState("");
  const [numQuestions, setNumQuestions] = useState(5);

  // Question & Recording state
  const [recording, setRecording] = useState(false);
  const [question, setQuestion] = useState("");
  const [sessionId, setSessionId] = useState(null);
  const [timeLeft, setTimeLeft] = useState(120);
  const [questionNum, setQuestionNum] = useState(1);
  const [totalQuestions, setTotalQuestions] = useState(5);
  const [countdown, setCountdown] = useState(5);
  const [isProcessing, setIsProcessing] = useState(false);
  const [liveTranscript, setLiveTranscript] = useState("");

  // Summary page state
  const [summaryData, setSummaryData] = useState(null);

  // ================= CAMERA SETUP =================
  useEffect(() => {
    async function setupCamera() {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: { width: { ideal: 1280 }, height: { ideal: 720 } },
          audio: true,
        });
        streamRef.current = stream;
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
        }
      } catch (err) {
        console.error("Camera error:", err);
        alert("Failed to access camera. Please check permissions.");
      }
    }

    setupCamera();

    return () => {
      if (streamRef.current) {
        streamRef.current.getTracks().forEach(track => track.stop());
      }
    };
  }, []);

  // Keep camera when page switches
  useEffect(() => {
    if (videoRef.current && streamRef.current && page !== "results") {
      videoRef.current.srcObject = streamRef.current;
    }
  }, [page]);

  // ================= TEXT-TO-SPEECH =================
  const speakQuestion = (text) => {
    if ('speechSynthesis' in window) {
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
    if (!jobDescription.trim()) {
      alert("Please paste a job description");
      return;
    }

    try {
      setIsProcessing(true);
      const res = await fetch("http://localhost:8000/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          job_description: jobDescription,
          resume: resume,
          num_questions: numQuestions
        }),
      });

      if (!res.ok) {
        throw new Error(`Server error: ${res.status}`);
      }

      const data = await res.json();
      setSessionId(data.session_id);
      setQuestion(data.question);
      setQuestionNum(data.question_number);
      setTotalQuestions(data.total_questions);
      setTimeLeft(120);
      setCountdown(5);
      setLiveTranscript("");
      setPage("question"); // Jump to question display page
    } catch (err) {
      console.error("Failed to start interview:", err);
      alert(`Error: ${err.message}`);
    } finally {
      setIsProcessing(false);
    }
  };

  // ================= RECORDING =================
  const startRecording = () => {
    if (!streamRef.current) {
      alert("Camera not ready");
      return;
    }

    // Start live speech recognition for subtitles
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

    recorder.ondataavailable = (e) => {
      chunks.push(e.data);
    };

    recorder.onstop = async () => {
      try {
        setIsProcessing(true);
        const blob = new Blob(chunks, { type: "video/webm" });
        const formData = new FormData();
        formData.append("file", blob);

        const res = await fetch(
          `http://localhost:8000/upload/${sessionId}`,
          {
            method: "POST",
            body: formData,
          }
        );

        if (!res.ok) {
          const errorData = await res.json().catch(() => ({}));
          throw new Error(errorData.error || `Upload failed: ${res.status}`);
        }

        const data = await res.json();
        
        if (data.interview_complete) {
          // Fetch full summary
          const summaryRes = await fetch(`http://localhost:8000/summary/${sessionId}`);
          if (!summaryRes.ok) {
            throw new Error("Failed to fetch summary");
          }
          const summary = await summaryRes.json();
          setSummaryData(summary);
          setPage("results");
        } else {
          // Continue to next question page
          setQuestion(data.next_question);
          setQuestionNum(data.question_number);
          setTimeLeft(120);
          setCountdown(5);
          setLiveTranscript("");
          setPage("question"); // Go back to question display page
        }
      } catch (err) {
        console.error("Upload error:", err);
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
    if (mediaRecorderRef.current) {
      mediaRecorderRef.current.stop();
    }
    if (recognitionRef.current) {
      recognitionRef.current.stop();
      recognitionRef.current = null;
    }
    setRecording(false);
    setLiveTranscript("");
  };

  // ================= TIMERS =================
  // Question page countdown (5 seconds before recording starts)
  useEffect(() => {
    if (page !== "question") return;
    
    setCountdown(5);
    const timer = setInterval(() => {
      setCountdown((prev) => {
        if (prev <= 1) {
          clearInterval(timer);
          setPage("recording");
          startRecording();
          return 5;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(timer);
  }, [page]);

  // Answer timer (120 seconds for recording)
  useEffect(() => {
    if (!recording || isProcessing) return;

    const timer = setInterval(() => {
      setTimeLeft((prev) => {
        if (prev <= 1) {
          stopRecording();
          return 120;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(timer);
  }, [recording, isProcessing]);

  // ================= UI =================

  // SETUP PAGE
  if (page === "setup") {
    return (
      <div style={styles.page}>
        <div style={styles.setupCard}>
          <h1 style={styles.title}>🎤 AI Technical Interview Coach</h1>
          <p style={styles.subtitle}>Practice interviews tailored to your target role</p>

          <div style={styles.formSection}>
            <label style={styles.label}>Job Description *</label>
            <textarea
              placeholder="Paste the job description here..."
              style={styles.textarea}
              value={jobDescription}
              onChange={(e) => setJobDescription(e.target.value)}
            />
          </div>

          <div style={styles.formSection}>
            <label style={styles.label}>Your Resume (Optional)</label>
            <textarea
              placeholder="Paste your resume or leave blank..."
              style={{...styles.textarea, minHeight: "100px"}}
              value={resume}
              onChange={(e) => setResume(e.target.value)}
            />
          </div>

          <div style={styles.formSection}>
            <label style={styles.label}>Number of Questions</label>
            <select 
              style={styles.select}
              value={numQuestions}
              onChange={(e) => setNumQuestions(parseInt(e.target.value))}
            >
              {[3, 4, 5, 6, 7, 8, 9, 10].map(n => (
                <option key={n} value={n}>{n} questions</option>
              ))}
            </select>
          </div>

          <div style={styles.videoPreview}>
            <video
              ref={videoRef}
              autoPlay
              muted
              style={{
                width: "100%",
                height: "100%",
                objectFit: "cover"
              }}
            />
          </div>
          <p style={styles.cameraLabel}>📹 Camera Preview</p>

          <button
            style={{...styles.primaryBtn, opacity: isProcessing ? 0.6 : 1}}
            onClick={startInterview}
            disabled={isProcessing}
          >
            {isProcessing ? "Starting..." : "Start Interview"}
          </button>
        </div>
      </div>
    );
  }

  // QUESTION PAGE - Display question with 5-second countdown
  if (page === "question") {
    return (
      <div style={styles.questionPage}>
        <div style={styles.questionNumLabel}>QUESTION {questionNum} OF {totalQuestions}</div>

        <div style={styles.bigQuestion}>{question}</div>

        <div style={styles.countdownBox}>
          <div style={styles.countdownLabel}>Recording starts in</div>
          <div style={styles.countdownNumber}>{countdown}</div>
          <div style={styles.progressBarBg}>
            <div style={{ ...styles.progressBarFill, width: `${(countdown / 5) * 100}%` }} />
          </div>
        </div>
      </div>
    );
  }

  // RECORDING PAGE - Record answer with video preview
  if (page === "recording") {
    return (
      <div style={styles.interviewContainer}>
        <div style={styles.timer}>⏱ {timeLeft}s</div>
        <div style={styles.avatar}>
          <div style={styles.avatarCircle}>AI</div>
          <div style={styles.avatarLabel}>Interviewer</div>
        </div>

        <div style={styles.camera}>
          <video
            ref={videoRef}
            autoPlay
            muted
            style={{ width: "100%", height: "100%", objectFit: "cover" }}
          />
          {liveTranscript !== "" && (
            <div style={styles.subtitleOverlay}>{liveTranscript}</div>
          )}
        </div>

        {/* Question area - scrollable if long */}
        <div style={styles.questionBox}>
          <div style={styles.questionBoxLabel}>CURRENT QUESTION</div>
          <h2 style={styles.questionText}>{question}</h2>
        </div>

        {/* Buttons always pinned at bottom */}
        <div style={styles.recordingBtnRow}>
          <button style={styles.redBtn} onClick={stopRecording}>
            ⏹️ Stop My Answer
          </button>
          <button style={styles.grayBtn} onClick={() => setPage("results")}>
            ✓ Finish Interview
          </button>
        </div>
      </div>
    );
  }

  // INTERVIEW PAGE (old, kept for reference - now replaced by question + recording)
  if (page === "interview") {
    return null; // This page is no longer used
  }

  // RESULTS PAGE
  if (page === "results" && summaryData) {
    return (
      <div style={styles.resultsPage}>
        <div style={styles.resultsContainer}>
          <h1 style={styles.resultsTitle}>🎉 Interview Complete!</h1>
          
          {/* Overall Score */}
          <div style={styles.scoreCard}>
            <div style={styles.scoreValue}>{summaryData.overall_score}%</div>
            <div style={styles.scoreLabel}>Overall Score</div>
          </div>

          {/* Encouraging Message */}
          <div style={styles.messageBox}>
            <p>{summaryData.encouraging_message}</p>
          </div>

          {/* Summary Table */}
          <h2>Interview Summary</h2>
          <div style={styles.tableWrapper}>
            <table style={styles.resultsTable}>
              <thead>
                <tr style={styles.tableHeader}>
                  <th>Q#</th>
                  <th>Question</th>
                  <th>Your Answer</th>
                  <th>Score</th>
                  <th>Strengths</th>
                  <th>Improvements</th>
                  <th>Video</th>
                </tr>
              </thead>
              <tbody>
                {summaryData.interview_history.map((item, idx) => (
                  <tr key={idx} style={styles.tableRow}>
                    <td style={styles.tableCell}>{item.question_number}</td>
                    <td style={styles.tableCell}>
                      <div style={{maxHeight: "80px", overflow: "auto"}}>
                        {item.question}
                      </div>
                    </td>
                    <td style={styles.tableCell}>
                      <div style={{maxHeight: "80px", overflow: "auto", fontSize: "13px"}}>
                        {item.transcript.substring(0, 100)}...
                      </div>
                    </td>
                    <td style={{...styles.tableCell, fontWeight: "bold", color: item.score >= 75 ? "#4CAF50" : item.score >= 60 ? "#FF9800" : "#F44336"}}>
                      {item.score}
                    </td>
                    <td style={styles.tableCell}>
                      <div style={{fontSize: "12px"}}>
                        {item.strengths}
                      </div>
                    </td>
                    <td style={styles.tableCell}>
                      <div style={{fontSize: "12px"}}>
                        {item.improvements}
                      </div>
                    </td>
                    <td style={styles.tableCell}>
                      {item.video_path ? (
                        <a 
                          href={item.video_path.startsWith('http') ? item.video_path : `${item.video_path}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          style={styles.videoLink}
                        >
                          📹 View ({item.video_size ? Math.round(item.video_size / 1024 / 1024 * 10) / 10 : '?'} MB)
                        </a>
                      ) : (
                        <span style={{color: '#999'}}>No video</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Actions */}
          <div style={styles.actionButtons}>
            <button
              style={styles.primaryBtn}
              onClick={() => {
                setPage("setup");
                setJobDescription("");
                setResume("");
                setNumQuestions(5);
                setSummaryData(null);
              }}
            >
              📋 Practice Again
            </button>
          </div>
        </div>
      </div>
    );
  }

  return null;
}

// ================= STYLES =================
const styles = {
  page: {
    minHeight: "100vh",
    backgroundColor: "#f5f5f5",
    display: "flex",
    justifyContent: "center",
    alignItems: "center",
    padding: "20px",
    fontFamily: "'Segoe UI', Tahoma, Geneva, Verdana, sans-serif"
  },
  setupCard: {
    width: "100%",
    maxWidth: "700px",
    background: "white",
    padding: "40px",
    borderRadius: "12px",
    boxShadow: "0 4px 12px rgba(0,0,0,0.1)",
    display: "flex",
    flexDirection: "column",
    gap: "20px"
  },
  title: {
    textAlign: "center",
    fontSize: "32px",
    margin: "0 0 5px 0",
    color: "#1E88E5"
  },
  subtitle: {
    textAlign: "center",
    fontSize: "14px",
    color: "#666",
    margin: 0
  },
  formSection: {
    display: "flex",
    flexDirection: "column",
    gap: "8px"
  },
  label: {
    fontWeight: "600",
    fontSize: "14px",
    color: "#333"
  },
  textarea: {
    minHeight: "150px",
    padding: "12px",
    borderRadius: "8px",
    border: "1px solid #ddd",
    fontFamily: "inherit",
    fontSize: "14px",
    resize: "vertical"
  },
  select: {
    padding: "10px 12px",
    borderRadius: "8px",
    border: "1px solid #ddd",
    fontSize: "14px",
    fontFamily: "inherit",
    cursor: "pointer"
  },
  videoPreview: {
    width: "100%",
    aspectRatio: "16 / 9",
    backgroundColor: "#000",
    borderRadius: "8px",
    overflow: "hidden"
  },
  cameraLabel: {
    textAlign: "center",
    margin: "0",
    fontSize: "12px",
    color: "#666"
  },
  primaryBtn: {
    padding: "12px 24px",
    backgroundColor: "#1E88E5",
    color: "white",
    border: "none",
    borderRadius: "8px",
    cursor: "pointer",
    fontSize: "16px",
    fontWeight: "600",
    transition: "background-color 0.3s"
  },

  // INTERVIEW PAGE
  interviewPage: {
    width: "100%",
    height: "100vh",
    backgroundColor: "#f5f5f5",
    display: "flex",
    flexDirection: "column",
    position: "relative",
    overflow: "hidden"
  },
  layoutContainer: {
    flex: 1,
    display: "flex",
    flexDirection: "column",
    overflow: "hidden"
  },
  timer: {
    position: "fixed",
    top: "20px",
    left: "20px",
    backgroundColor: "#000",
    color: "#fff",
    padding: "8px 15px",
    borderRadius: "20px",
    zIndex: "100",
    fontSize: "16px",
    fontWeight: "bold"
  },
  avatar: {
    position: "fixed",
    top: "20px",
    right: "20px",
    zIndex: "100",
    textAlign: "center"
  },
  avatarCircle: {
    width: "60px",
    height: "60px",
    borderRadius: "50%",
    backgroundColor: "#FF6B6B",
    color: "white",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontSize: "24px",
    fontWeight: "bold",
    boxShadow: "0 2px 8px rgba(0,0,0,0.15)"
  },
  avatarLabel: {
    fontSize: "12px",
    color: "#666",
    marginTop: "5px"
  },
  progress: {
    position: "fixed",
    bottom: "20px",
    right: "20px",
    backgroundColor: "#1E88E5",
    color: "white",
    padding: "8px 12px",
    borderRadius: "20px",
    fontSize: "14px",
    fontWeight: "bold",
    zIndex: "100"
  },
  cameraContainer: {
    flex: "0 0 35%",
    backgroundColor: "#000",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    borderBottom: "2px solid #ddd"
  },
  controlPanel: {
    flex: "1",
    backgroundColor: "white",
    padding: "20px",
    boxShadow: "0 -4px 12px rgba(0,0,0,0.1)",
    display: "flex",
    flexDirection: "column",
    gap: "15px",
    overflow: "auto"
  },
  questionBox: {
    display: "flex",
    flexDirection: "column",
    gap: "15px"
  },
  questionText: {
    margin: "0",
    fontSize: "18px",
    color: "#333",
    lineHeight: "1.4"
  },
  buttonGroup: {
    display: "flex",
    gap: "10px",
    flexWrap: "wrap",
    alignItems: "center"
  },
  greenBtn: {
    padding: "10px 20px",
    backgroundColor: "#4CAF50",
    color: "white",
    border: "none",
    borderRadius: "8px",
    cursor: "pointer",
    fontSize: "14px",
    fontWeight: "600",
    transition: "background-color 0.3s"
  },
  redBtn: {
    padding: "10px 20px",
    backgroundColor: "#F44336",
    color: "white",
    border: "none",
    borderRadius: "8px",
    cursor: "pointer",
    fontSize: "14px",
    fontWeight: "600",
    transition: "background-color 0.3s"
  },
  processingText: {
    color: "#FF9800",
    fontSize: "13px",
    fontWeight: "600"
  },
  prepTimerText: {
    margin: "0",
    padding: "10px",
    backgroundColor: "#FFF9C4",
    borderLeft: "4px solid #FBC02D",
    color: "#333",
    fontSize: "14px",
    fontWeight: "500",
    borderRadius: "4px"
  },
  preparingText: {
    color: "#FF9800",
    fontSize: "14px",
    fontWeight: "600",
    padding: "8px 12px",
    backgroundColor: "#FFF3E0",
    borderRadius: "6px"
  },
  timerInfo: {
    margin: "0"
  },

  // QUESTION PAGE
  questionPage: {
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "center",
    minHeight: "100vh",
    gap: "2rem",
    padding: "40px",
    backgroundColor: "#f5f5f5"
  },
  questionNumLabel: {
    fontSize: "13px",
    color: "#888",
    letterSpacing: "0.08em",
    fontWeight: "600"
  },
  bigQuestion: {
    fontSize: "28px",
    fontWeight: "500",
    textAlign: "center",
    maxWidth: "640px",
    lineHeight: "1.6",
    color: "#1a1a1a"
  },
  countdownBox: {
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    gap: "12px",
    marginTop: "2rem"
  },
  countdownLabel: {
    fontSize: "14px",
    color: "#888",
    textAlign: "center"
  },
  countdownNumber: {
    fontSize: "56px",
    fontWeight: "500",
    color: "#1E88E5",
    textAlign: "center"
  },
  progressBarBg: {
    width: "200px",
    height: "4px",
    backgroundColor: "#eee",
    borderRadius: "4px",
    overflow: "hidden"
  },
  progressBarFill: {
    height: "100%",
    backgroundColor: "#1E88E5",
    borderRadius: "4px",
    transition: "width 1s linear"
  },

  // RECORDING PAGE
  interviewContainer: {
    width: "100%",
    height: "100vh",
    display: "flex",
    flexDirection: "column",
    backgroundColor: "#fff",
    position: "relative",
    overflow: "hidden"
  },
  camera: {
    flex: "1 1 0",
    minHeight: "0",
    backgroundColor: "#000",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    position: "relative",
    borderBottom: "2px solid #ddd"
  },
  subtitleOverlay: {
    position: "absolute",
    bottom: "20px",
    left: "50%",
    transform: "translateX(-50%)",
    backgroundColor: "rgba(0,0,0,0.6)",
    color: "white",
    padding: "8px 16px",
    borderRadius: "8px",
    fontSize: "15px",
    maxWidth: "80%",
    textAlign: "center",
    pointerEvents: "none",
    zIndex: "50"
  },
  questionBox: {
    flex: "0 0 auto",
    maxHeight: "50vh",
    backgroundColor: "white",
    padding: "20px 24px 12px 24px",
    boxShadow: "0 -4px 12px rgba(0,0,0,0.1)",
    display: "flex",
    flexDirection: "column",
    gap: "10px",
    overflowY: "auto",
    borderTop: "3px solid #1E88E5"
  },
  questionBoxLabel: {
    fontSize: "12px",
    color: "#1E88E5",
    fontWeight: "600",
    letterSpacing: "0.08em",
    marginBottom: "2px"
  },
  questionText: {
    fontSize: "22px",
    fontWeight: "500",
    lineHeight: "1.6",
    margin: 0,
    color: "#1a1a1a"
  },
  recordingBtnRow: {
    flex: "0 0 auto",
    display: "flex",
    gap: "10px",
    padding: "12px 24px",
    backgroundColor: "white",
    borderTop: "1px solid #eee"
  },
  grayBtn: {
    padding: "10px 20px",
    backgroundColor: "#999",
    color: "white",
    border: "none",
    borderRadius: "8px",
    cursor: "pointer",
    fontSize: "14px",
    fontWeight: "600",
    transition: "background-color 0.3s"
  },

  // RESULTS PAGE
  resultsPage: {
    minHeight: "100vh",
    backgroundColor: "#f5f5f5",
    padding: "40px 20px"
  },
  resultsContainer: {
    maxWidth: "1200px",
    margin: "0 auto",
    backgroundColor: "white",
    padding: "40px",
    borderRadius: "12px",
    boxShadow: "0 4px 12px rgba(0,0,0,0.1)"
  },
  resultsTitle: {
    textAlign: "center",
    fontSize: "32px",
    color: "#1E88E5",
    marginBottom: "20px"
  },
  scoreCard: {
    textAlign: "center",
    padding: "30px",
    backgroundColor: "#f0f7ff",
    borderRadius: "12px",
    marginBottom: "30px",
    border: "2px solid #1E88E5"
  },
  scoreValue: {
    fontSize: "48px",
    fontWeight: "bold",
    color: "#1E88E5"
  },
  scoreLabel: {
    fontSize: "16px",
    color: "#666",
    marginTop: "10px"
  },
  messageBox: {
    padding: "20px",
    backgroundColor: "#e8f5e9",
    borderLeft: "4px solid #4CAF50",
    borderRadius: "4px",
    marginBottom: "30px",
    fontSize: "16px",
    color: "#333",
    lineHeight: "1.6"
  },
  tableWrapper: {
    overflowX: "auto",
    marginBottom: "30px"
  },
  resultsTable: {
    width: "100%",
    borderCollapse: "collapse",
    fontSize: "13px"
  },
  tableHeader: {
    backgroundColor: "#1E88E5",
    color: "white"
  },
  tableRow: {
    borderBottom: "1px solid #ddd"
  },
  tableCell: {
    padding: "12px",
    textAlign: "left",
    verticalAlign: "top"
  },
  videoLink: {
    color: "#1E88E5",
    textDecoration: "none",
    fontWeight: "600"
  },
  actionButtons: {
    display: "flex",
    gap: "15px",
    justifyContent: "center"
  }
};

export default App;