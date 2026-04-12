/**
 * Navbar.jsx - Navigation bar with user info and quota display
 */

import React, { useState, useEffect } from "react";
import "./Navbar.css";
import { logout, fetchWithAuth } from "../utils/auth";

const API_BASE = process.env.REACT_APP_API_BASE || "http://localhost:8000";

export default function Navbar() {
  const [user, setUser] = useState(null);
  const [quota, setQuota] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchUserInfo();
  }, []);

  const fetchUserInfo = async () => {
    try {
      // Get user from localStorage (stored during auth)
      const userStr = localStorage.getItem("user_info");
      if (userStr) {
        setUser(JSON.parse(userStr));
      }

      // Get quota from API
      const response = await fetchWithAuth(`${API_BASE}/user/quota`);
      const data = await response.json();
      setQuota(data);
    } catch (err) {
      console.error("Failed to fetch user info:", err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <nav className="navbar">
      <div className="navbar-brand">
        <a href="/">AI Interview Coach</a>
      </div>

      <div className="navbar-right">
        {!loading && user && quota && (
          <>
            <div className="user-info">
              <span className="username">{user.username}</span>
              <span className={`plan-badge ${quota.plan}`}>
                {quota.plan.toUpperCase()}
              </span>
            </div>

            {quota.plan === "free" && (
              <div className="quota-display">
                <span>{quota.requests_used_today} / {quota.limit} requests today</span>
              </div>
            )}
          </>
        )}

        <button className="logout-button" onClick={logout}>
          Logout
        </button>
      </div>
    </nav>
  );
}
