/**
 * InterviewPage.jsx - Main interview page
 * Features: Question display, Monaco Editor for coding, textarea for text answers,
 * timer, and answer submission with follow-up questions for resume/behavioral interviews
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
  const [answerText, setAnswerText] = useState("");
  const [code, setCode] = useState(
    LANGUAGES.python.template
  );
  const [selectedLanguage, setSelectedLanguage] = useState("python");
  const [loading, setLoading] = useState(false);
  const [timeRemaining, setTimeRemaining] = useState(null);
  const [showQuotaModal, setShowQuotaModal] = useState(false);
  const [quotaExceeded, setQuotaExceeded] = useState(false);
  const timerIntervalRef = useRef(null);
  const editorRef = useRef(null);
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

  const handleEditorDidMount = (editor) => {
    /**
     * Called when Monaco Editor finishes loading.
     * Stores editor reference and focuses it for keyboard input.
     */
    editorRef.current = editor;
    // Use setTimeout to ensure focus happens after render
    setTimeout(() => {
      editor.focus();
    }, 100);
  };

  const submitAnswer = async () => {
    const isCoding = currentQuestion.interview_type === "coding";
    let userAnswer = isCoding ? code : answerText;

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
          question: currentQuestion.question,
          question_focus: currentQuestion.question_focus,
          interview_type: currentQuestion.interview_type,
          user_answer: userAnswer,
          depth_layer: currentQuestion.depth_layer || 1,
        }),
      });

      const data = await response.json();
      console.log("Answer submission response:", data);
      console.log("Next question:", data.next_question);

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
        console.log("Loading next question:", data.next_question);
        setCurrentQuestion(data.next_question);
        setCurrentQuestionId(`q-${Math.random()}`);
        setAnswerText("");
        setCode(LANGUAGES[selectedLanguage].template);
      } else {
        // Interview complete
        console.log("No next question, completing interview");
        completeInterview();
      }
    } catch (err) {
      alert("Error: " + err.message);
      console.error("Error submitting answer:", err);
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
              <div className="editor-container">
                <Editor
                  height="100%"
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
                    scrollbar: {
                      vertical: "auto",
                      horizontal: "auto",
                    },
                  }}
                />
              </div>
            </div>
          )}

          {/* Answer Panel (for non-coding) */}
          {!isCoding && (
            <div className="answer-panel">
              <h3>Your Answer</h3>
              <textarea
                className="transcript-display"
                value={answerText}
                onChange={(e) => setAnswerText(e.target.value)}
                placeholder="Type your answer here..."
                rows={12}
              />
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
              (!isCoding && !answerText.trim()) ||
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
