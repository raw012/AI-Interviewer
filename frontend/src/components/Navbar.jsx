/**
 * Navbar.jsx - Navigation bar with user info and quota display
 * Features: LinkedIn-style design, mobile hamburger menu, responsive layout
 */

import React, { useState, useEffect } from "react";
import "./Navbar.css";
import { logout, fetchWithAuth } from "../utils/auth";

const API_BASE = process.env.REACT_APP_API_BASE || "http://localhost:8000";

export default function Navbar() {
  const [user, setUser] = useState(null);
  const [quota, setQuota] = useState(null);
  const [loading, setLoading] = useState(true);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  useEffect(() => {
    fetchUserInfo();
  }, []);

  const fetchUserInfo = async () => {
    try {
      const userStr = localStorage.getItem("user_info");
      if (userStr) {
        setUser(JSON.parse(userStr));
      }

      const response = await fetchWithAuth(`${API_BASE}/user/quota`);
      const data = await response.json();
      setQuota(data);
    } catch (err) {
      console.error("Failed to fetch user info:", err);
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = () => {
    setMobileMenuOpen(false);
    logout();
  };

  return (
    <nav className="navbar">
      <div className="navbar-container">
        {/* Logo */}
        <div className="navbar-brand">
          <a href="/">🎯 Interview Coach</a>
        </div>

        {/* Mobile Menu Toggle */}
        <button 
          className="hamburger-menu visible-mobile"
          onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
          aria-label="Toggle menu"
        >
          <span></span>
          <span></span>
          <span></span>
        </button>

        {/* Right Section - Desktop always visible, Mobile toggle */}
        <div className={`navbar-right ${mobileMenuOpen ? 'mobile-open' : ''}`}>
          {!loading && user && quota && (
            <>
              <div className="user-info">
                <div className="user-details">
                  <span className="username">{user.username}</span>
                  <span className={`plan-badge ${quota.plan}`}>
                    {quota.plan.toUpperCase()}
                  </span>
                </div>
                {quota.plan === "free" && (
                  <span className="quota-display">
                    {quota.requests_used_today} / {quota.limit} used today
                  </span>
                )}
              </div>
            </>
          )}

          <button 
            className="logout-button" 
            onClick={handleLogout}
          >
            Logout
          </button>
        </div>
      </div>
    </nav>
  );
}
