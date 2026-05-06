/**
 * InterviewPage.jsx - Main interview page with state machine
 * States: loading → questioning → thinking → answering → evaluating → feedback → questioning (loop) → completed
 * Features: TTS, countdown timers, single-question card UI
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
  
  // Current state machine
  const [state, setState] = useState("loading"); // loading | questioning | thinking | answering | evaluating | feedback | completed
  const [currentQuestion, setCurrentQuestion] = useState(null);
  const [feedback, setFeedback] = useState("");
  const [score, setScore] = useState(0);
  
  // Answer input
  const [answerText, setAnswerText] = useState("");
  const [code, setCode] = useState(LANGUAGES.python.template);
  const [selectedLanguage, setSelectedLanguage] = useState("python");
  
  // Timers
  const [timeRemaining, setTimeRemaining] = useState(null);
  const [thinkingCountdown, setThinkingCountdown] = useState(5);
  const [answerCountdown, setAnswerCountdown] = useState(120);
  
  // UI state
  const [showQuotaModal, setShowQuotaModal] = useState(false);
  const [quotaExceeded, setQuotaExceeded] = useState(false);
  const [questionsAnswered, setQuestionsAnswered] = useState(0);
  
  // Refs
  const timerIntervalRef = useRef(null);
  const thinkingIntervalRef = useRef(null);
  const answerIntervalRef = useRef(null);
  const editorRef = useRef(null);
  const ttsRef = useRef(null);

  // Load session on mount
  useEffect(() => {
    const stored = localStorage.getItem("interview_session");
    if (stored) {
      const data = JSON.parse(stored);
      setSessionData(data);
      if (data.questions && data.questions.length > 0) {
        setCurrentQuestion(data.questions[0]);
        // Start session timer
        const minutes = data.duration_minutes || 30;
        setTimeRemaining(minutes * 60);
        setState("questioning");
      }
    }
  }, []);

  // Session timer effect (counts down from duration)
  useEffect(() => {
    if (timeRemaining === null || state === "completed") return;

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
  }, [timeRemaining, state]);

  // Thinking countdown effect
  useEffect(() => {
    if (state !== "thinking") return;

    if (thinkingCountdown <= 0) {
      // Transition to answering after thinking countdown
      setThinkingCountdown(5); // Reset for next use
      setState("answering");
      setAnswerCountdown(120); // Reset answer timer
      return;
    }

    thinkingIntervalRef.current = setInterval(() => {
      setThinkingCountdown((prev) => {
        if (prev <= 1) {
          setState("answering");
          setAnswerCountdown(120);
          return 5;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(thinkingIntervalRef.current);
  }, [state, thinkingCountdown]);

  // Answer countdown effect (2 minute timer)
  useEffect(() => {
    if (state !== "answering") return;

    if (answerCountdown <= 0) {
      // Auto-submit when timer hits 0
      handleSubmitAnswer();
      return;
    }

    answerIntervalRef.current = setInterval(() => {
      setAnswerCountdown((prev) => {
        if (prev <= 1) {
          // Will auto-submit via the answerCountdown <= 0 check above
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(answerIntervalRef.current);
  }, [state, answerCountdown]);

  // Auto-transition from feedback to questioning after 3 seconds
  useEffect(() => {
    if (state !== "feedback") return;

    const timer = setTimeout(() => {
      setState("questioning");
      setAnswerText("");
      setCode(LANGUAGES[selectedLanguage].template);
    }, 3000);

    return () => clearTimeout(timer);
  }, [state, selectedLanguage]);

  // TTS with auto-transition to thinking
  useEffect(() => {
    if (state === "questioning" && currentQuestion) {
      speakQuestion();
    }
  }, [state, currentQuestion]);

  const formatTime = (seconds) => {
    if (!seconds) return "0:00";
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, "0")}`;
  };

  const speakQuestion = () => {
    const speechText = `${currentQuestion.question}. Focus: ${currentQuestion.question_focus}`;
    const utterance = new SpeechSynthesisUtterance(speechText);
    
    // Try to find female voice
    const voices = speechSynthesis.getVoices();
    const femaleVoice = voices.find(
      (v) => v.name.includes("Female") || v.name.includes("woman")
    ) || voices.find((v) => v.lang === "en-US");
    
    if (femaleVoice) {
      utterance.voice = femaleVoice;
    }
    
    utterance.rate = 0.95;
    utterance.pitch = 1;
    utterance.volume = 1;

    // After TTS finishes, transition to thinking
    utterance.onend = () => {
      setState("thinking");
      setThinkingCountdown(5);
    };

    speechSynthesis.cancel(); // Clear any previous speech
    ttsRef.current = utterance;
    speechSynthesis.speak(utterance);
  };

  const handleEditorDidMount = (editor) => {
    editorRef.current = editor;
    setTimeout(() => {
      editor.focus();
    }, 100);
  };

  const handleSubmitAnswer = async () => {
    const isCoding = currentQuestion.interview_type === "coding";
    let userAnswer = isCoding ? code : answerText;

    if (!userAnswer.trim()) {
      // Empty submission: for coding, force score 0; for text, skip
      if (!isCoding) {
        userAnswer = "[No answer provided]";
      }
    }

    setState("evaluating");

    try {
      const response = await fetchWithAuth(`${API_BASE}/interview/answer`, {
        method: "POST",
        body: JSON.stringify({
          session_id: sessionData.session_id,
          question_id: currentQuestion.id || `q-${Math.random()}`,
          question: currentQuestion.question,
          question_focus: currentQuestion.question_focus,
          interview_type: currentQuestion.interview_type,
          user_answer: userAnswer,
          depth_layer: currentQuestion.depth_layer || 1,
          domain: sessionData.domain,
        }),
      });

      const data = await response.json();

      if (response.status === 429) {
        setQuotaExceeded(true);
        setShowQuotaModal(true);
        setState("questioning");
        return;
      }

      if (!response.ok) {
        alert("Error: " + data.detail);
        setState("questioning");
        return;
      }

      // Show feedback
      setScore(data.score);
      setFeedback(data.feedback);
      setQuestionsAnswered((prev) => prev + 1);

      if (data.next_question) {
        // Load next question, will auto-transition after 3 seconds
        setCurrentQuestion(data.next_question);
        setState("feedback");
      } else {
        // Interview complete
        setState("completed");
      }
    } catch (err) {
      alert("Error: " + err.message);
      setState("questioning");
    }
  };

  const handleEndInterview = async () => {
    setState("loading");

    if (!sessionData) return;

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
        setState("questioning");
      }
    } catch (err) {
      alert("Error: " + err.message);
      setState("questioning");
    }
  };

  if (!sessionData) {
    return <div className="loading-screen">Loading...</div>;
  }

  if (state === "completed") {
    return (
      <div className="interview-page">
        <Navbar />
        <div className="completion-screen">
          <h1>Interview Complete! 🎉</h1>
          <p>You've answered {questionsAnswered} questions.</p>
          <button onClick={() => window.location.href = `/summary/${sessionData.session_id}`}>
            View Summary
          </button>
        </div>
      </div>
    );
  }

  if (!currentQuestion) {
    return (
      <div className="interview-page">
        <Navbar />
        <div className="loading-screen">Loading question...</div>
      </div>
    );
  }

  const isCoding = currentQuestion.interview_type === "coding";
  const showFollowUpTag = currentQuestion.depth_layer > 1;

  return (
    <div className="interview-page">
      <Navbar />

      {showQuotaModal && (
        <QuotaExceededModal onClose={() => setShowQuotaModal(false)} />
      )}

      {/* LinkedIn-style single question card */}
      <div className="interview-container">
        {/* Header */}
        <div className="interview-header">
          <div className="header-left">
            <h3>{currentQuestion.interview_type.toUpperCase()} Interview</h3>
            {showFollowUpTag && (
              <span className="followup-tag">
                Follow-up · Layer {currentQuestion.depth_layer} / 5
              </span>
            )}
          </div>
          <div className="header-center">
            <div className="timer" style={{ color: timeRemaining < 300 ? "#e74c3c" : "#2c3e50" }}>
              {formatTime(timeRemaining)}
            </div>
          </div>
          <div className="header-right">
            <button className="end-button" onClick={handleEndInterview}>
              End Interview
            </button>
          </div>
        </div>

        {/* Question Card */}
        <div className="question-card">
          <div className="question-content">
            <p className="question-text">{currentQuestion.question}</p>
            <p className="question-focus">
              <strong>Focus:</strong> {currentQuestion.question_focus}
            </p>
          </div>

          {/* State-specific answer section */}
          <div className="answer-section">
            {state === "thinking" && (
              <div className="thinking-state">
                <div className="countdown-display">
                  <div className="countdown-number">{thinkingCountdown}</div>
                  <p>Take a moment to think...</p>
                </div>
              </div>
            )}

            {state === "questioning" && (
              <div className="questioning-state">
                <div className="tts-playing">
                  <div className="spinner"></div>
                  <p>Reading question aloud...</p>
                </div>
              </div>
            )}

            {state === "answering" && (
              <div className="answering-state">
                <div className="answer-timer">
                  <span className={answerCountdown < 30 ? "warning" : ""}>
                    {formatTime(answerCountdown)}
                  </span>
                </div>

                {isCoding ? (
                  <div className="editor-panel">
                    <div className="editor-header">
                      <h4>Write Your Solution</h4>
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
                    <div className="editor-container">
                      <Editor
                        height="300px"
                        language={selectedLanguage}
                        value={code}
                        onChange={(value) => setCode(value || "")}
                        onMount={handleEditorDidMount}
                        theme="vs-light"
                        options={{
                          readOnly: false,
                          automaticLayout: true,
                          minimap: { enabled: false },
                          fontSize: 14,
                          scrollBeyondLastLine: false,
                          wordWrap: "on",
                          formatOnPaste: true,
                          insertSpaces: true,
                          tabSize: 2,
                          lineNumbers: "on",
                          scrollbar: { vertical: "auto", horizontal: "auto" },
                        }}
                      />
                    </div>
                  </div>
                ) : (
                  <textarea
                    className="answer-textarea"
                    placeholder="Type your answer here..."
                    value={answerText}
                    onChange={(e) => setAnswerText(e.target.value)}
                  />
                )}

                <button
                  className="submit-button"
                  onClick={handleSubmitAnswer}
                  disabled={state === "evaluating"}
                >
                  {state === "evaluating" ? "Submitting..." : "Submit Answer"}
                </button>
              </div>
            )}

            {state === "evaluating" && (
              <div className="evaluating-state">
                <div className="spinner"></div>
                <p>AI is evaluating your answer...</p>
              </div>
            )}

            {state === "feedback" && (
              <div className="feedback-state">
                <div className={`score-badge score-${score >= 70 ? "good" : score >= 50 ? "fair" : "poor"}`}>
                  <div className="score-value">{score}</div>
                  <div className="score-label">/100</div>
                </div>
                <div className="feedback-text">
                  <p>{feedback}</p>
                </div>
                <p className="auto-advance-notice">Loading next question...</p>
              </div>
            )}
          </div>
        </div>

        {/* Question counter */}
        <div className="question-counter">
          Question {questionsAnswered + 1}
        </div>
      </div>
    </div>
  );
}
