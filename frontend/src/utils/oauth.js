/**
 * OAuth utilities for handling Google, Apple, and Facebook login
 * Sends tokens to backend and manages authentication state
 */

import { setToken } from './auth';

const API_BASE = process.env.REACT_APP_API_BASE || 'http://localhost:8000';

/**
 * Show a toast notification (with react-toastify if available)
 * Falls back to console.log if toast library not available
 */
export function showToast(message, type = 'info') {
  try {
    // Try to use react-toastify if it's imported in parent component
    // Components using this can wrap their App with ToastContainer
    const toast = window.__toastNotification;
    if (toast && typeof toast[type] === 'function') {
      toast[type](message, {
        position: 'top-right',
        autoClose: 4000,
        hideProgressBar: false,
        closeOnClick: true,
        pauseOnHover: true,
        draggable: true,
      });
    } else {
      // Fallback: simple console log
      console.log(`[${type.toUpperCase()}] ${message}`);
    }
  } catch (e) {
    // If anything fails, just log to console
    console.log(`[${type.toUpperCase()}] ${message}`);
  }
}

/**
 * Handle successful OAuth login
 * Sends token to backend and saves JWT
 * @param {string} provider - 'google', 'apple', or 'facebook'
 * @param {string} tokenData - ID token or access token
 * @returns {Promise<Object>} Response data from backend with JWT token
 */
async function handleOAuthSuccess(provider, tokenData) {
  try {
    const endpoint = `/auth/${provider}`;
    const payload = provider === 'facebook' 
      ? { access_token: tokenData }
      : { id_token: tokenData };

    const response = await fetch(`${API_BASE}${endpoint}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.detail || `${provider} login failed`);
    }

    // Save JWT token
    setToken(data.token);
    
    // Show success message (alternative: use console if toast not available)
    const message = `Welcome ${data.username}!`;
    showToast(message, 'success');

    // Redirect to setup page after brief delay
    setTimeout(() => {
      window.location.href = '/setup';
    }, 500);

    return data;
  } catch (error) {
    const message = error.message || `${provider} login failed`;
    showToast(message, 'error');
    throw error;
  }
}

/**
 * Google Sign-In handler
 * Called when user successfully authenticates with Google
 * @param {Object} credentialResponse - Response from GoogleLogin component
 * @returns {Promise<Object>} User data and JWT token
 */
export async function handleGoogleLogin(credentialResponse) {
  if (!credentialResponse?.credential) {
    const errorMessage = 'Google login cancelled';
    showToast(errorMessage, 'error');
    throw new Error(errorMessage);
  }

  return handleOAuthSuccess('google', credentialResponse.credential);
}

/**
 * Apple Sign-In handler
 * Called when user successfully authenticates with Apple
 * @param {string} idToken - ID token from Apple
 * @returns {Promise<Object>} User data and JWT token
 */
export async function handleAppleLogin(idToken) {
  if (!idToken) {
    const errorMessage = 'Apple login cancelled';
    showToast(errorMessage, 'error');
    throw new Error(errorMessage);
  }

  return handleOAuthSuccess('apple', idToken);
}

/**
 * Facebook Login handler
 * Called when user successfully logs in with Facebook
 * @param {Object} response - Response from FacebookLogin component
 * @returns {Promise<Object>} User data and JWT token
 */
export async function handleFacebookLogin(response) {
  if (!response?.accessToken) {
    const errorMessage = 'Facebook login cancelled';
    showToast(errorMessage, 'error');
    throw new Error(errorMessage);
  }

  return handleOAuthSuccess('facebook', response.accessToken);
}

/**
 * Setup Apple Sign-In JavaScript SDK
 * Call this once when component mounts
 * Loads SDK from Apple's CDN if not already loaded
 */
export function initializeAppleSignIn() {
  if (typeof window === 'undefined') return;

  // Check if SDK is already loaded
  if (window.AppleID?.auth) {
    console.log('Apple SDK already loaded');
    return;
  }

  // Check if SDK script is already loaded
  if (document.querySelector('script[src*="appleid"]')) {
    console.log('Apple SDK script already present, waiting for initialization...');
    // Give it a moment to load
    setTimeout(() => {
      if (window.AppleID?.auth) {
        performAppleInitialization();
      }
    }, 500);
    return;
  }

  // Load the Apple SDK if not present
  const script = document.createElement('script');
  script.src = 'https://appleid.cdn-apple.com/appleauth/static/jsappleauth.js';
  script.async = true;
  script.onload = () => {
    console.log('Apple SDK loaded successfully');
    performAppleInitialization();
  };
  script.onerror = () => {
    console.warn('Failed to load Apple SDK from CDN');
  };
  document.head.appendChild(script);
}

/**
 * Perform Apple SDK initialization after SDK is loaded
 */
function performAppleInitialization() {
  if (typeof window === 'undefined' || !window.AppleID) {
    console.log('AppleID SDK not yet available');
    return;
  }

  try {
    window.AppleID.auth.init({
      clientId: process.env.REACT_APP_APPLE_CLIENT_ID || 'com.interviewer.web',
      teamId: process.env.REACT_APP_APPLE_TEAM_ID,
      keyId: process.env.REACT_APP_APPLE_KEY_ID,
      redirectURI: `${window.location.origin}/auth/callback`,
      scope: 'email name',
      usePopup: true,
    });
    console.log('Apple Sign-In initialized successfully');
  } catch (error) {
    console.warn('Apple Sign-In initialization failed:', error.message);
  }
}

/**
 * Setup event listener for Apple Sign-In
 * Call after initializeAppleSignIn() to add event handlers
 * @param {Function} onSuccess - Callback when sign-in succeeds
 * @param {Function} onError - Callback when sign-in fails
 * @returns {Object|null} Event handler object or null if not available
 */
export function setupAppleSignInListener(onSuccess, onError) {
  if (typeof window === 'undefined' || !window.AppleID) {
    console.warn('AppleID SDK not available');
    return null;
  }

  const handleSuccess = (event) => {
    try {
      const authorization = event.detail?.authorization;
      if (authorization?.id_token) {
        onSuccess(authorization.id_token);
      }
    } catch (error) {
      console.error('Error handling Apple Sign-In success:', error);
      onError?.(error);
    }
  };

  const handleError = (event) => {
    try {
      const errorMessage = event.detail?.error || 'Unknown Apple Sign-In error';
      console.error('Apple Sign-In error:', errorMessage);
      onError?.(errorMessage);
    } catch (error) {
      console.error('Error handling Apple Sign-In error:', error);
      onError?.(error);
    }
  };

  // Add event listeners to Apple Sign-In button elements
  const appleSignInElement = document.getElementById('appleid-signin');
  const appleSignUpElement = document.getElementById('appleid-signin-signup');

  if (appleSignInElement) {
    appleSignInElement.addEventListener('AppleIDSignInOnSuccess', handleSuccess);
    appleSignInElement.addEventListener('AppleIDSignInOnError', handleError);
  }

  if (appleSignUpElement) {
    appleSignUpElement.addEventListener('AppleIDSignInOnSuccess', handleSuccess);
    appleSignUpElement.addEventListener('AppleIDSignInOnError', handleError);
  }

  return { handleSuccess, handleError };
}

/**
 * Configure react-toastify if available
 * Call this from App.js or main component
 */
export function configureToastNotifications(toast) {
  if (toast) {
    window.__toastNotification = toast;
  }
}

