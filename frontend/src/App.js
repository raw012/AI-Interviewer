/**
 * App.jsx - Main application routing and layout
 * Routes: / → Auth if not authenticated, else Setup
 *         /setup → Setup page
 *         /interview/:sessionId → Interview page
 *         /summary/:sessionId → Summary page
 *         /pricing → Pricing page
 */

import React from "react";
import { BrowserRouter as Router, Routes, Route, Navigate } from "react-router-dom";
import { GoogleOAuthProvider } from "@react-oauth/google";
import "./App.css";

import { isAuthenticated } from "./utils/auth";
import AuthPage from "./pages/AuthPage";
import SetupPage from "./pages/SetupPage";
import InterviewPage from "./pages/InterviewPage";
import SummaryPage from "./pages/SummaryPage";
import PricingPage from "./pages/PricingPage";

// Protected Route Component
function ProtectedRoute({ children }) {
  if (!isAuthenticated()) {
    return <Navigate to="/auth" replace />;
  }
  return children;
}

function App() {
  return (
    <GoogleOAuthProvider clientId={process.env.REACT_APP_GOOGLE_CLIENT_ID || ""}>
      <Router>
        <Routes>
          {/* Auth Route */}
          <Route path="/auth" element={<AuthPage />} />

          {/* Protected Routes */}
          <Route
            path="/setup"
            element={
              <ProtectedRoute>
                <SetupPage />
              </ProtectedRoute>
            }
          />

          <Route
            path="/interview/:sessionId"
            element={
              <ProtectedRoute>
                <InterviewPage />
              </ProtectedRoute>
            }
          />

          <Route
            path="/summary/:sessionId"
            element={
              <ProtectedRoute>
                <SummaryPage />
              </ProtectedRoute>
            }
          />

          <Route
            path="/pricing"
            element={
              <ProtectedRoute>
                <PricingPage />
              </ProtectedRoute>
            }
          />

          {/* Root redirect */}
          <Route
            path="/"
            element={
              isAuthenticated() ? (
                <Navigate to="/setup" replace />
              ) : (
                <Navigate to="/auth" replace />
            )
          }
        />

        {/* 404 */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Router>
    </GoogleOAuthProvider>
  );
}

export default App;
