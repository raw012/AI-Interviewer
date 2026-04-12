/**
 * PricingPage.jsx - Stripe pricing and upgrade page (placeholder)
 * TODO: Implement Stripe integration
 */

import React from "react";
import "./PricingPage.css";
import Navbar from "../components/Navbar";

export default function PricingPage() {
  return (
    <div className="pricing-page">
      <Navbar />

      <div className="pricing-container">
        <h1>Choose Your Plan</h1>
        <p className="subtitle">Upgrade to unlock unlimited AI requests</p>

        <div className="pricing-cards">
          {/* Free Plan */}
          <div className="pricing-card">
            <div className="plan-name">Free</div>
            <div className="plan-price">
              <span className="amount">$0</span>
              <span className="period">/month</span>
            </div>
            <ul className="plan-features">
              <li>✓ 10 AI requests per day</li>
              <li>✓ All interview types</li>
              <li>✓ 15/30/60 min sessions</li>
              <li>✗ No priority support</li>
            </ul>
            <button className="btn-current">Current Plan</button>
          </div>

          {/* Pro Plan */}
          <div className="pricing-card featured">
            <div className="plan-badge">POPULAR</div>
            <div className="plan-name">Pro</div>
            <div className="plan-price">
              <span className="amount">$9.99</span>
              <span className="period">/month</span>
            </div>
            <ul className="plan-features">
              <li>✓ Unlimited AI requests</li>
              <li>✓ All interview types</li>
              <li>✓ Priority support</li>
              <li>✓ Advanced analytics</li>
              <li>✓ Export to PDF</li>
            </ul>
            <button className="btn-upgrade" onClick={() => alert("TODO: Stripe integration")}>
              Upgrade Now
            </button>
          </div>
        </div>

        <div className="todo-notice">
          <h3>🚧 Under Development</h3>
          <p>
            Stripe payment integration is coming soon. For now, please contact us
            to upgrade your account.
          </p>
        </div>
      </div>
    </div>
  );
}
