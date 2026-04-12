/**
 * InterviewPage.jsx - Main interview page
 * Features: Audio recording, question display, Monaco Editor for coding,
 * timer, and answer submission
 */

import React, { useState, useEffect, useRef } from "react";
import Editor from "@monaco-editor/react";
import "./InterviewPage.css";
import Navbar from "../components/Navbar";
import QuotaExceededModal from "../components/QuotaExceededModal";
import { fetchWithAuth } from "../utils/auth";

const API_BASE = process.env.REACT_APP_API_BASE || "http://localhost:8000";

const LANGUAGES = {
  python: { label: "Python", template: "# Write your solution here\n" },
  java: { label: "Java", template: "public class Solution {\n    // Your code here\n}\n" },
  cpp: { label: "C++", template: "#include <iostream>\nusing namespace std;\n\nint main() {\n    // Your code here\n    return 0;\n}\n" },
  javascript: { label: "JavaScript", template: "// Write your solution here\n" },
};

export default function InterviewPage() {
  const sessionIdFromUrl = window.location.pathname.split("/").pop();
  const [sessionData, setSessionData] = useState(null);
  const [currentQuestion, setCurrentQuestion] = useState(null);
  const [currentQuestionId, setCurrentQuestionId] = useState(null);
  const [recording, setRecording] = useState(false);
  const [audioBlob, setAudioBlob] = useState(null);
  const [transcriptText, setTranscriptText] = useState("");
  const [code, setCode] = useState(
    LANGUAGES.python.template
  );
  const [selectedLanguage, setSelectedLanguage] = useState("python");
  const [loading, setLoading] = useState(false);
  const [timeRemaining, setTimeRemaining] = useState(null);
  const [showQuotaModal, setShowQuotaModal] = useState(false);
  const [quotaExceeded, setQuotaExceeded] = useState(false);
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const timerIntervalRef = useRef(null);

  // Load session on mount
  useEffect(() => {
    const stored = localStorage.getItem("interview_session");
    if (stored) {
      const data = JSON.parse(stored);
      setSessionData(data);
      if (data.questions && data.questions.length > 0) {
        setCurrentQuestion(data.questions[0]);
        setCurrentQuestionId(data.questions[0].id || `q-${Math.random()}`);
        // Start timer
        const minutes = data.duration_minutes || 30;
        setTimeRemaining(minutes * 60);
      }
    }
  }, []);

  // Timer effect
  useEffect(() => {
    if (timeRemaining === null) return;

    timerIntervalRef.current = setInterval(() => {
      setTimeRemaining((prev) => {
        if (prev <= 1) {
          clearInterval(timerIntervalRef.current);
          handleEndInterview();
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(timerIntervalRef.current);
  }, [timeRemaining]);

  const formatTime = (seconds) => {
    if (!seconds) return "0:00";
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, "0")}`;
  };

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = new MediaRecorder(stream);
      mediaRecorderRef.current = mediaRecorder;
      audioChunksRef.current = [];

      mediaRecorder.ondataavailable = (event) => {
        audioChunksRef.current.push(event.data);
      };

      mediaRecorder.onstop = () => {
        const blob = new Blob(audioChunksRef.current, { type: "audio/mp3" });
        setAudioBlob(blob);
      };

      mediaRecorder.start();
      setRecording(true);
    } catch (err) {
      alert("Microphone access denied. Please enable microphone access.");
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current) {
      mediaRecorderRef.current.stop();
      mediaRecorderRef.current.stream.getTracks().forEach((track) => track.stop());
      setRecording(false);
    }
  };

  const transcribeAudio = async () => {
    if (!audioBlob) return;

    setLoading(true);
    const formData = new FormData();
    formData.append("file", audioBlob, "audio.mp3");

    try {
      const response = await fetchWithAuth(`${API_BASE}/interview/upload-audio`, {
        method: "POST",
        body: formData,
      });

      const data = await response.json();

      if (response.ok) {
        setTranscriptText(data.transcript);
      } else {
        alert("Transcription failed: " + data.detail);
      }
    } catch (err) {
      alert("Error: " + err.message);
    } finally {
      setLoading(false);
    }
  };

  const submitAnswer = async () => {
    let userAnswer = transcriptText;

    // For coding, use code instead of transcript
    if (currentQuestion.interview_type === "coding") {
      userAnswer = code;
    }

    if (!userAnswer.trim()) {
      alert("Please provide an answer before submitting");
      return;
    }

    setLoading(true);

    try {
      const response = await fetchWithAuth(`${API_BASE}/interview/answer`, {
        method: "POST",
        body: JSON.stringify({
          session_id: sessionData.session_id,
          question_id: currentQuestionId,
          interview_type: currentQuestion.interview_type,
          user_answer: userAnswer,
          depth_layer: currentQuestion.depth_layer || 1,
        }),
      });

      const data = await response.json();

      if (response.status === 429) {
        setQuotaExceeded(true);
        setShowQuotaModal(true);
        setLoading(false);
        return;
      }

      if (!response.ok) {
        alert("Error: " + data.detail);
        setLoading(false);
        return;
      }

      // Show feedback briefly then load next question
      alert(
        `Score: ${data.score}/100\nFeedback: ${data.feedback}`
      );

      if (data.next_question) {
        setCurrentQuestion(data.next_question);
        setCurrentQuestionId(`q-${Math.random()}`);
        setTranscriptText("");
        setCode(LANGUAGES[selectedLanguage].template);
        setAudioBlob(null);
      } else {
        // Interview complete
        completeInterview();
      }
    } catch (err) {
      alert("Error: " + err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleEndInterview = async () => {
    await completeInterview();
  };

  const completeInterview = async () => {
    if (!sessionData) return;

    setLoading(true);

    try {
      const response = await fetchWithAuth(`${API_BASE}/interview/complete`, {
        method: "POST",
        body: JSON.stringify({ session_id: sessionData.session_id }),
      });

      const data = await response.json();

      if (response.ok) {
        window.location.href = `/summary/${sessionData.session_id}`;
      } else {
        alert("Error completing interview: " + data.detail);
      }
    } catch (err) {
      alert("Error: " + err.message);
    } finally {
      setLoading(false);
    }
  };

  if (!sessionData || !currentQuestion) {
    return <div>Loading...</div>;
  }

  const isCoding = currentQuestion.interview_type === "coding";

  return (
    <div className="interview-page">
      <Navbar />

      {showQuotaModal && (
        <QuotaExceededModal onClose={() => setShowQuotaModal(false)} />
      )}

      <div className="interview-container">
        {/* Header with Timer */}
        <div className="interview-header">
          <h1>{currentQuestion.interview_type.toUpperCase()} Interview</h1>
          <div className="timer">
            <span className={timeRemaining < 300 ? "warning" : ""}>
              {formatTime(timeRemaining)}
            </span>
          </div>
          <button className="end-button" onClick={handleEndInterview}>
            End Interview
          </button>
        </div>

        {/* Main Content */}
        <div className={`interview-content ${isCoding ? "has-editor" : ""}`}>
          {/* Question Panel */}
          <div className="question-panel">
            <div className="question-header">
              <h2>Question</h2>
              {currentQuestion.depth_layer > 1 && (
                <span className="depth-badge">
                  Follow-up (Layer {currentQuestion.depth_layer}/3)
                </span>
              )}
            </div>
            <div className="question-text">{currentQuestion.question}</div>
            <p className="focus-hint">
              <strong>Focus:</strong> {currentQuestion.question_focus}
            </p>
          </div>

          {/* Editor Panel (for coding only) */}
          {isCoding && (
            <div className="editor-panel">
              <div className="editor-header">
                <h3>Write Your Solution</h3>
                <select
                  value={selectedLanguage}
                  onChange={(e) => {
                    setSelectedLanguage(e.target.value);
                    setCode(LANGUAGES[e.target.value].template);
                  }}
                >
                  {Object.entries(LANGUAGES).map(([key, val]) => (
                    <option key={key} value={key}>
                      {val.label}
                    </option>
                  ))}
                </select>
              </div>
              <Editor
                height="400"
                language={selectedLanguage}
                value={code}
                onChange={(value) => setCode(value || "")}
                theme="vs-light"
                options={{
                  minimap: { enabled: false },
                  fontSize: 14,
                }}
              />
            </div>
          )}

          {/* Answer Panel (for non-coding) */}
          {!isCoding && (
            <div className="answer-panel">
              <h3>Your Answer</h3>

              <div className="audio-section">
                <div className="audio-controls">
                  {!recording ? (
                    <button
                      className="btn-record"
                      onClick={startRecording}
                      disabled={loading}
                    >
                      🎤 Start Recording
                    </button>
                  ) : (
                    <button
                      className="btn-stop"
                      onClick={stopRecording}
                      disabled={loading}
                    >
                      ⏹ Stop Recording
                    </button>
                  )}

                  {audioBlob && (
                    <>
                      <button
                        className="btn-transcribe"
                        onClick={transcribeAudio}
                        disabled={loading}
                      >
                        📝 Transcribe
                      </button>
                      <audio
                        controls
                        src={URL.createObjectURL(audioBlob)}
                        className="audio-player"
                      />
                    </>
                  )}
                </div>
              </div>

              {transcriptText && (
                <textarea
                  className="transcript-display"
                  value={transcriptText}
                  onChange={(e) => setTranscriptText(e.target.value)}
                  placeholder="Transcript will appear here..."
                  rows={8}
                />
              )}
            </div>
          )}
        </div>

        {/* Submit Button */}
        <div className="interview-footer">
          <button
            className="submit-button"
            onClick={submitAnswer}
            disabled={
              loading ||
              (!isCoding && !transcriptText.trim()) ||
              (isCoding && !code.trim())
            }
          >
            {loading ? "Processing..." : "Submit Answer"}
          </button>
        </div>
      </div>
    </div>
  );
}
