/**
 * Authentication utilities for token and credential management.
 */

const TOKEN_KEY = "auth_token";

/**
 * Get JWT token from localStorage
 */
export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

/**
 * Store JWT token in localStorage
 */
export function setToken(token) {
  localStorage.setItem(TOKEN_KEY, token);
}

/**
 * Get authorization headers with JWT token
 */
export function authHeaders() {
  const token = getToken();
  if (!token) {
    return {};
  }
  return {
    Authorization: `Bearer ${token}`,
  };
}

/**
 * Check if user is authenticated
 */
export function isAuthenticated() {
  return !!getToken();
}

/**
 * Clear token and redirect to auth page
 */
export function logout() {
  localStorage.removeItem(TOKEN_KEY);
  window.location.href = "/auth";
}

/**
 * Make an authenticated API call
 */
export async function fetchWithAuth(url, options = {}) {
  const headers = {
    "Content-Type": "application/json",
    ...authHeaders(),
    ...options.headers,
  };

  const response = await fetch(url, {
    ...options,
    headers,
  });

  // If 401, user is not authenticated
  if (response.status === 401) {
    logout();
    throw new Error("Unauthorized");
  }

  return response;
}
