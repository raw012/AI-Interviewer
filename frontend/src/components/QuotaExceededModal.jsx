/**
 * QuotaExceededModal.jsx - Modal shown when free user exceeds daily quota
 */

import React from "react";
import "./QuotaExceededModal.css";

export default function QuotaExceededModal({ onClose }) {
  return (
    <div className="modal-overlay">
      <div className="modal">
        <h2>Daily Quota Exceeded</h2>
        <p>
          You've used all 10 free AI requests for today. Your quota will reset at
          midnight UTC.
        </p>
        <p className="modal-subtitle">Upgrade to Pro for unlimited access.</p>

        <div className="modal-actions">
          <button className="btn-secondary" onClick={onClose}>
            OK
          </button>
          <button className="btn-primary" onClick={() => (window.location.href = "/pricing")}>
            Upgrade to Pro
          </button>
        </div>
      </div>
    </div>
  );
}
