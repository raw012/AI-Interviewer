/**
 * SummaryPage.jsx - Post-interview results and review
 * Displays all Q&A pairs with scores, feedback, grouped by interview type
 */

import React, { useState, useEffect } from "react";
import "./SummaryPage.css";
import Navbar from "../components/Navbar";
import { fetchWithAuth } from "../utils/auth";

const API_BASE = process.env.REACT_APP_API_BASE || "http://localhost:8000";

export default function SummaryPage() {
  const sessionId = window.location.pathname.split("/").pop();
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    fetchSummary();
  }, []);

  const fetchSummary = async () => {
    try {
      const response = await fetchWithAuth(
        `${API_BASE}/interview/summary/${sessionId}`
      );

      if (!response.ok) {
        setError("Failed to load summary");
        setLoading(false);
        return;
      }

      const data = await response.json();
      setSummary(data);
    } catch (err) {
      setError("Error: " + err.message);
    } finally {
      setLoading(false);
    }
  };

  const getScoreBadgeClass = (score) => {
    if (score >= 70) return "score-good";
    if (score >= 50) return "score-fair";
    return "score-poor";
  };

  const groupedByType = (qaPairs) => {
    const grouped = {};
    qaPairs.forEach((qa) => {
      if (!grouped[qa.interview_type]) {
        grouped[qa.interview_type] = [];
      }
      grouped[qa.interview_type].push(qa);
    });
    return grouped;
  };

  if (loading) {
    return <div className="loading">Loading summary...</div>;
  }

  if (error) {
    return (
      <div className="summary-page">
        <Navbar />
        <div className="error-message">{error}</div>
      </div>
    );
  }

  if (!summary) {
    return <div>No data available</div>;
  }

  const grouped = groupedByType(summary.qa_pairs);

  return (
    <div className="summary-page">
      <Navbar />

      <div className="summary-container">
        <h1>Interview Summary</h1>

        {/* Overall Score */}
        <div className="overall-section">
          <div className="score-card">
            <div className="score-label">Overall Score</div>
            <div className={`score-value ${getScoreBadgeClass(summary.overall_score)}`}>
              {Math.round(summary.overall_score)}
            </div>
            <div className="score-out-of">/ 100</div>
          </div>
        </div>

        {/* Results by Interview Type */}
        {Object.entries(grouped).map(([type, pairs]) => (
          <div key={type} className="results-section">
            <h2>{type.toUpperCase()} Interview</h2>

            <table className="results-table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Question</th>
                  <th>Key Focus</th>
                  <th>Your Answer</th>
                  <th>AI Feedback</th>
                  <th>Score</th>
                </tr>
              </thead>
              <tbody>
                {pairs.map((qa, idx) => (
                  <tr key={`${type}-${idx}`}>
                    <td className="number">{idx + 1}</td>
                    <td className="question">{qa.question}</td>
                    <td className="focus">{qa.key_focus}</td>
                    <td className="answer">
                      <div className="answer-text">{qa.your_answer}</div>
                    </td>
                    <td className="feedback">{qa.ai_feedback}</td>
                    <td className="score">
                      <span className={`score-badge ${getScoreBadgeClass(qa.score)}`}>
                        {qa.score}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ))}

        {/* Action Buttons */}
        <div className="actions-section">
          <button
            className="btn-download"
            onClick={() => {
              // TODO: Implement PDF download
              alert("PDF download coming soon!");
            }}
          >
            📥 Download Summary as PDF
          </button>
          <button
            className="btn-retake"
            onClick={() => (window.location.href = "/setup")}
          >
            🔄 Take Another Interview
          </button>
        </div>
      </div>
    </div>
  );
}
