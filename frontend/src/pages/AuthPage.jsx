/**
 * AuthPage.jsx - User authentication (signup/login)
 * Two tabs: Sign Up and Log In with email/password and social OAuth options
 * Supports: Email/Password, Google, Apple, Facebook
 * Redirects to setup page on successful auth
 */

import React, { useState, useEffect } from "react";
import { GoogleLogin } from "@react-oauth/google";
import FacebookLogin from "react-facebook-login/dist/facebook-login-render-props";
import "./AuthPage.css";
import { setToken, isAuthenticated } from "../utils/auth";
import {
  handleGoogleLogin,
  handleAppleLogin,
  handleFacebookLogin,
  initializeAppleSignIn,
  showToast,
} from "../utils/oauth";

const API_BASE = process.env.REACT_APP_API_BASE || "http://localhost:8000";
const FACEBOOK_APP_ID = process.env.REACT_APP_FACEBOOK_APP_ID || "";

export default function AuthPage() {
  const [activeTab, setActiveTab] = useState("login"); // "login" or "signup"
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  
  // OAuth loading states (per provider)
  const [oauthLoading, setOauthLoading] = useState({
    google: false,
    apple: false,
    facebook: false,
  });

  // Login form state
  const [loginData, setLoginData] = useState({ email: "", password: "" });

  // Signup form state
  const [signupData, setSignupData] = useState({
    username: "",
    email: "",
    password: "",
    confirmPassword: "",
  });

  // Redirect if already authenticated
  useEffect(() => {
    if (isAuthenticated()) {
      window.location.href = "/setup";
    }
  }, []);

  // Initialize Apple Sign-In on mount
  useEffect(() => {
    initializeAppleSignIn();
  }, []);

  // Handle Apple Sign-In success
  const handleAppleSuccess = async (idToken) => {
    setOauthLoading((prev) => ({ ...prev, apple: true }));
    try {
      await handleAppleLogin(idToken);
    } catch (error) {
      setError(error.message || "Apple login failed");
    } finally {
      setOauthLoading((prev) => ({ ...prev, apple: false }));
    }
  };

  // Manual Apple button click handler
  const handleAppleButtonClick = async () => {
    if (typeof window === 'undefined' || !window.AppleID?.auth) {
      showToast('Apple Sign-In SDK not available. Please refresh the page.', 'error');
      return;
    }

    try {
      setOauthLoading((prev) => ({ ...prev, apple: true }));
      const response = await window.AppleID.auth.signIn();
      if (response?.authorization?.id_token) {
        await handleAppleSuccess(response.authorization.id_token);
      }
    } catch (error) {
      showToast(error?.message || 'Apple Sign-In failed. Please try again.', 'error');
      setOauthLoading((prev) => ({ ...prev, apple: false }));
    }
  };

  // Handle Google success
  const handleGoogleSuccess = async (credentialResponse) => {
    setOauthLoading((prev) => ({ ...prev, google: true }));
    try {
      await handleGoogleLogin(credentialResponse);
    } catch (error) {
      setError(error.message || "Google login failed");
    } finally {
      setOauthLoading((prev) => ({ ...prev, google: false }));
    }
  };

  // Handle Facebook success
  const handleFacebookSuccess = async (response) => {
    setOauthLoading((prev) => ({ ...prev, facebook: true }));
    try {
      await handleFacebookLogin(response);
    } catch (error) {
      setError(error.message || "Facebook login failed");
    } finally {
      setOauthLoading((prev) => ({ ...prev, facebook: false }));
    }
  };

  const handleLoginChange = (e) => {
    const { name, value } = e.target;
    setLoginData((prev) => ({ ...prev, [name]: value }));
    setError("");
  };

  const handleSignupChange = (e) => {
    const { name, value } = e.target;
    setSignupData((prev) => ({ ...prev, [name]: value }));
    setError("");
  };

  const handleLoginSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError("");

    try {
      const response = await fetch(`${API_BASE}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(loginData),
      });

      const data = await response.json();

      if (!response.ok) {
        setError(data.detail || "Login failed");
        setLoading(false);
        return;
      }

      // Store token and redirect
      setToken(data.token);
      showToast(`Welcome back ${data.username}!`, "success");
      setTimeout(() => {
        window.location.href = "/setup";
      }, 300);
    } catch (err) {
      setError("Network error: " + err.message);
      setLoading(false);
    }
  };

  const handleSignupSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError("");

    // Validation
    if (signupData.password !== signupData.confirmPassword) {
      setError("Passwords do not match");
      setLoading(false);
      return;
    }

    if (signupData.password.length < 8) {
      setError("Password must be at least 8 characters");
      setLoading(false);
      return;
    }

    try {
      const response = await fetch(`${API_BASE}/auth/signup`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: signupData.username,
          email: signupData.email,
          password: signupData.password,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        setError(data.detail || "Signup failed");
        setLoading(false);
        return;
      }

      // Store token and redirect
      setToken(data.token);
      showToast(`Welcome ${data.username}! Account created successfully.`, "success");
      setTimeout(() => {
        window.location.href = "/setup";
      }, 300);
    } catch (err) {
      setError("Network error: " + err.message);
      setLoading(false);
    }
  };

  const isAnyOAuthLoading = Object.values(oauthLoading).some((val) => val);

  return (
    <div className="auth-page">
      <div className="auth-container">
        <h1>AI Interview Coach</h1>
        <p className="subtitle">Prepare for your next technical interview</p>

        <div className="auth-tabs">
          <button
            className={`tab ${activeTab === "login" ? "active" : ""}`}
            onClick={() => {
              setActiveTab("login");
              setError("");
            }}
          >
            Log In
          </button>
          <button
            className={`tab ${activeTab === "signup" ? "active" : ""}`}
            onClick={() => {
              setActiveTab("signup");
              setError("");
            }}
          >
            Sign Up
          </button>
        </div>

        {error && <div className="error-message">{error}</div>}

        {activeTab === "login" && (
          <form onSubmit={handleLoginSubmit} className="auth-form">
            <div className="form-group">
              <label htmlFor="login-email">Email</label>
              <input
                id="login-email"
                type="email"
                name="email"
                placeholder="your@email.com"
                value={loginData.email}
                onChange={handleLoginChange}
                disabled={isAnyOAuthLoading}
                required
              />
            </div>

            <div className="form-group">
              <label htmlFor="login-password">Password</label>
              <input
                id="login-password"
                type="password"
                name="password"
                placeholder="••••••••"
                value={loginData.password}
                onChange={handleLoginChange}
                disabled={isAnyOAuthLoading}
                required
              />
            </div>

            <button 
              type="submit" 
              disabled={loading || isAnyOAuthLoading} 
              className="submit-button"
            >
              {loading ? "Logging in..." : "Log In"}
            </button>

            {/* Divider */}
            <div className="divider">
              <span>or continue with</span>
            </div>

            {/* Social Login Buttons */}
            <div className="social-buttons">
              {/* Google Button */}
              <div className="google-button-wrapper">
                <GoogleLogin
                  onSuccess={handleGoogleSuccess}
                  onError={() => setError("Google login failed")}
                  useOneTap={false}
                  text="signin_with"
                  theme="outline"
                  size="large"
                  width="100%"
                  locale="en_US"
                />
              </div>

              {/* Apple Button */}
              <button
                type="button"
                className="social-button apple-button"
                onClick={handleAppleButtonClick}
                disabled={isAnyOAuthLoading}
                aria-label="Sign in with Apple"
              >
                <svg
                  className="social-icon"
                  viewBox="0 0 24 24"
                  fill="currentColor"
                >
                  <path d="M17.05 20.28c-.98.95-2.05.88-3.08.4-1.09-.5-2.08-.48-3.24 0-1.44.62-2.2.44-3.06-.4C2.79 15.25 3.51 7.59 9.05 7.31c1.35.05 2.29.89 3.08.89.79 0 2.18-1.1 3.69-.95 2.08.15 3.71 1.21 4.6 3.05-4.36 2.41-3.55 8.26.48 9.68zm-5.4-18.3c.34-1.09.18-2.08-.1-2.53.55.05 1.19.36 1.68 1.02.87.96.73 2.35.36 2.62-.87-.53-1.6-1.18-1.94-2.11z" />
                </svg>
                <span>Sign in with Apple</span>
              </button>

              {/* Facebook Button */}
              <FacebookLogin
                appId={FACEBOOK_APP_ID}
                autoLoad={false}
                fields="name,email,picture"
                scope="public_profile,email"
                callback={handleFacebookSuccess}
                textButton="Sign in with Facebook"
                render={(renderProps) => (
                  <button
                    type="button"
                    className="social-button facebook-button"
                    onClick={renderProps.onClick}
                    disabled={isAnyOAuthLoading || renderProps.isProcessing}
                    aria-label="Sign in with Facebook"
                  >
                    <svg
                      className="social-icon"
                      viewBox="0 0 24 24"
                      fill="currentColor"
                    >
                      <path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z" />
                    </svg>
                    <span>Sign in with Facebook</span>
                  </button>
                )}
              />
            </div>
          </form>
        )}

        {activeTab === "signup" && (
          <form onSubmit={handleSignupSubmit} className="auth-form">
            <div className="form-group">
              <label htmlFor="signup-username">Username</label>
              <input
                id="signup-username"
                type="text"
                name="username"
                placeholder="myusername"
                value={signupData.username}
                onChange={handleSignupChange}
                disabled={isAnyOAuthLoading}
                required
              />
            </div>

            <div className="form-group">
              <label htmlFor="signup-email">Email</label>
              <input
                id="signup-email"
                type="email"
                name="email"
                placeholder="your@email.com"
                value={signupData.email}
                onChange={handleSignupChange}
                disabled={isAnyOAuthLoading}
                required
              />
            </div>

            <div className="form-group">
              <label htmlFor="signup-password">Password</label>
              <input
                id="signup-password"
                type="password"
                name="password"
                placeholder="••••••••"
                value={signupData.password}
                onChange={handleSignupChange}
                disabled={isAnyOAuthLoading}
                required
              />
            </div>

            <div className="form-group">
              <label htmlFor="signup-confirm">Confirm Password</label>
              <input
                id="signup-confirm"
                type="password"
                name="confirmPassword"
                placeholder="••••••••"
                value={signupData.confirmPassword}
                onChange={handleSignupChange}
                disabled={isAnyOAuthLoading}
                required
              />
            </div>

            <button 
              type="submit" 
              disabled={loading || isAnyOAuthLoading} 
              className="submit-button"
            >
              {loading ? "Creating account..." : "Sign Up"}
            </button>

            {/* Divider */}
            <div className="divider">
              <span>or sign up with</span>
            </div>

            {/* Social Login Buttons */}
            <div className="social-buttons">
              {/* Google Button */}
              <div className="google-button-wrapper">
                <GoogleLogin
                  onSuccess={handleGoogleSuccess}
                  onError={() => setError("Google login failed")}
                  useOneTap={false}
                  text="signup_with"
                  theme="outline"
                  size="large"
                  width="100%"
                  locale="en_US"
                />
              </div>

              {/* Apple Button */}
              <button
                type="button"
                className="social-button apple-button"
                onClick={handleAppleButtonClick}
                disabled={isAnyOAuthLoading}
                aria-label="Sign up with Apple"
              >
                <svg
                  className="social-icon"
                  viewBox="0 0 24 24"
                  fill="currentColor"
                >
                  <path d="M17.05 20.28c-.98.95-2.05.88-3.08.4-1.09-.5-2.08-.48-3.24 0-1.44.62-2.2.44-3.06-.4C2.79 15.25 3.51 7.59 9.05 7.31c1.35.05 2.29.89 3.08.89.79 0 2.18-1.1 3.69-.95 2.08.15 3.71 1.21 4.6 3.05-4.36 2.41-3.55 8.26.48 9.68zm-5.4-18.3c.34-1.09.18-2.08-.1-2.53.55.05 1.19.36 1.68 1.02.87.96.73 2.35.36 2.62-.87-.53-1.6-1.18-1.94-2.11z" />
                </svg>
                <span>Sign up with Apple</span>
              </button>

              {/* Facebook Button */}
              <FacebookLogin
                appId={FACEBOOK_APP_ID}
                autoLoad={false}
                fields="name,email,picture"
                scope="public_profile,email"
                callback={handleFacebookSuccess}
                textButton="Sign up with Facebook"
                render={(renderProps) => (
                  <button
                    type="button"
                    className="social-button facebook-button"
                    onClick={renderProps.onClick}
                    disabled={isAnyOAuthLoading || renderProps.isProcessing}
                    aria-label="Sign up with Facebook"
                  >
                    <svg
                      className="social-icon"
                      viewBox="0 0 24 24"
                      fill="currentColor"
                    >
                      <path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z" />
                    </svg>
                    <span>Sign up with Facebook</span>
                  </button>
                )}
              />
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
