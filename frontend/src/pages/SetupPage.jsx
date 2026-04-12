/**
 * SetupPage.jsx - Pre-interview configuration screen
 * Allows user to select interview types, upload resume, enter job description, etc.
 */

import React, { useState } from "react";
import "./SetupPage.css";
import Navbar from "../components/Navbar";
import { fetchWithAuth } from "../utils/auth";

const API_BASE = process.env.REACT_APP_API_BASE || "http://localhost:8000";

const INTERVIEW_TYPES = [
  {
    id: "coding",
    label: "Coding Interview",
    description: "30 min, LeetCode-style, includes code editor",
  },
  {
    id: "resume",
    label: "Resume-Based Interview",
    description: "AI asks from your resume, 3 layers deep",
  },
  {
    id: "technical",
    label: "Technical Interview",
    description: "CS fundamentals based on your background",
  },
  {
    id: "behavioral",
    label: "Behavioral Interview",
    description: "Behavioral questions from job description",
  },
];

const DURATIONS = [15, 30, 60];

export default function SetupPage() {
  const [selectedTypes, setSelectedTypes] = useState([]);
  const [resumeText, setResumeText] = useState("");
  const [jobDescription, setJobDescription] = useState("");
  const [targetCompany, setTargetCompany] = useState("");
  const [targetPosition, setTargetPosition] = useState("");
  const [duration, setDuration] = useState(30);
  const [customInstructions, setCustomInstructions] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const toggleInterviewType = (typeId) => {
    setSelectedTypes((prev) =>
      prev.includes(typeId) ? prev.filter((t) => t !== typeId) : [...prev, typeId]
    );
  };

  const handleStartInterview = async () => {
    setError("");

    // Validation
    if (selectedTypes.length === 0) {
      setError("Please select at least one interview type");
      return;
    }

    if (selectedTypes.includes("resume") && !resumeText.trim()) {
      setError("Resume is required for Resume-Based interview");
      return;
    }

    if (selectedTypes.includes("technical") && !resumeText.trim()) {
      setError("Resume is required for Technical interview");
      return;
    }

    if (
      (selectedTypes.includes("technical") || selectedTypes.includes("behavioral")) &&
      !jobDescription.trim()
    ) {
      setError("Job Description is required for selected interview types");
      return;
    }

    if (selectedTypes.includes("coding") && (!targetCompany || !targetPosition)) {
      setError("Target Company and Position are required for Coding interview");
      return;
    }

    setLoading(true);

    try {
      const response = await fetchWithAuth(`${API_BASE}/interview/start`, {
        method: "POST",
        body: JSON.stringify({
          interview_types: selectedTypes,
          resume_text: resumeText,
          job_description: jobDescription,
          target_company: targetCompany,
          target_position: targetPosition,
          duration_minutes: duration,
          user_comments: customInstructions,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        setError(data.detail || "Failed to start interview");
        setLoading(false);
        return;
      }

      // Store session and navigate
      localStorage.setItem("interview_session", JSON.stringify(data));
      window.location.href = `/interview/${data.session_id}`;
    } catch (err) {
      setError("Error: " + err.message);
      setLoading(false);
    }
  };

  const needsResume =
    selectedTypes.includes("resume") || selectedTypes.includes("technical");
  const needsJobDescription =
    selectedTypes.includes("technical") || selectedTypes.includes("behavioral");
  const needsCodingDetails = selectedTypes.includes("coding");

  return (
    <div className="setup-page">
      <Navbar />
      <div className="setup-container">
        <h1>Prepare Your Interview</h1>

        {error && <div className="error-message">{error}</div>}

        {/* Section 1: Interview Type Selection */}
        <div className="setup-section">
          <h2>Interview Types</h2>
          <div className="interview-types">
            {INTERVIEW_TYPES.map((type) => (
              <label key={type.id} className="checkbox-item">
                <input
                  type="checkbox"
                  checked={selectedTypes.includes(type.id)}
                  onChange={() => toggleInterviewType(type.id)}
                />
                <div className="checkbox-content">
                  <div className="checkbox-label">{type.label}</div>
                  <div className="checkbox-description">{type.description}</div>
                </div>
              </label>
            ))}
          </div>
        </div>

        {/* Section 2: Resume Upload */}
        {needsResume && (
          <div className="setup-section">
            <h2>Your Resume</h2>
            <textarea
              className="textarea-input"
              placeholder="Paste your resume here or upload as text"
              value={resumeText}
              onChange={(e) => setResumeText(e.target.value)}
              rows={6}
            />
          </div>
        )}

        {/* Section 3: Job Description */}
        {needsJobDescription && (
          <div className="setup-section">
            <h2>Job Description</h2>
            <textarea
              className="textarea-input"
              placeholder="Paste the job description here"
              value={jobDescription}
              onChange={(e) => setJobDescription(e.target.value)}
              rows={6}
            />
          </div>
        )}

        {/* Section 4: Coding Interview Details */}
        {needsCodingDetails && (
          <div className="setup-section">
            <h2>Target Role</h2>
            <div className="row">
              <div className="col-50">
                <label htmlFor="company">Company</label>
                <input
                  id="company"
                  type="text"
                  placeholder="e.g., Google"
                  value={targetCompany}
                  onChange={(e) => setTargetCompany(e.target.value)}
                />
              </div>
              <div className="col-50">
                <label htmlFor="position">Position</label>
                <input
                  id="position"
                  type="text"
                  placeholder="e.g., Software Engineer"
                  value={targetPosition}
                  onChange={(e) => setTargetPosition(e.target.value)}
                />
              </div>
            </div>
            <p className="note">*Coding interviews are always 30 minutes</p>
          </div>
        )}

        {/* Section 5: Interview Duration */}
        {!selectedTypes.includes("coding") && (
          <div className="setup-section">
            <h2>Interview Duration</h2>
            <div className="radio-group">
              {DURATIONS.map((d) => (
                <label key={d} className="radio-item">
                  <input
                    type="radio"
                    name="duration"
                    value={d}
                    checked={duration === d}
                    onChange={(e) => setDuration(parseInt(e.target.value))}
                  />
                  {d} minutes
                </label>
              ))}
            </div>
          </div>
        )}

        {/* Section 6: Custom Instructions */}
        <div className="setup-section">
          <h2>Custom Instructions (Optional)</h2>
          <textarea
            className="textarea-input"
            placeholder="e.g., Focus on my distributed systems experience, skip frontend questions"
            value={customInstructions}
            onChange={(e) => setCustomInstructions(e.target.value)}
            rows={3}
          />
        </div>

        {/* Start Interview Button */}
        <div className="setup-section">
          <button
            className="start-button"
            onClick={handleStartInterview}
            disabled={loading}
          >
            {loading ? "Starting Interview..." : "Start Interview"}
          </button>
        </div>
      </div>
    </div>
  );
}
