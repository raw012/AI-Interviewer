/** API client: bearer token storage and JSON helpers for the studio backend. */
export const API_URL =
  process.env.REACT_APP_API_URL ||
  (process.env.NODE_ENV === "development" ? "http://localhost:8000" : window.location.origin);

const TOKEN_KEY = "interviewer_token";

export const tokenStore = {
  get: () => {
    try { return localStorage.getItem(TOKEN_KEY) || ""; } catch { return ""; }
  },
  set: (value) => {
    try { value ? localStorage.setItem(TOKEN_KEY, value) : localStorage.removeItem(TOKEN_KEY); } catch { /* private mode */ }
  },
};

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

export async function request(path, { method = "GET", body, raw = false, form } = {}) {
  const headers = new Headers();
  const token = tokenStore.get();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  let payload;
  if (form) payload = form;
  else if (body !== undefined) {
    headers.set("Content-Type", "application/json");
    payload = JSON.stringify(body);
  }
  const response = await fetch(`${API_URL}${path}`, { method, headers, body: payload });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    if (response.status === 401 && token) window.dispatchEvent(new Event("auth-expired"));
    throw new ApiError(data.detail || `Request failed (${response.status})`, response.status);
  }
  if (raw) return response;
  return response.json();
}

export const api = {
  get: (path) => request(path),
  post: (path, body = {}) => request(path, { method: "POST", body }),
  put: (path, body = {}) => request(path, { method: "PUT", body }),
  patch: (path, body = {}) => request(path, { method: "PATCH", body }),
  del: (path, body) => request(path, { method: "DELETE", body }),
  upload: (path, form) => request(path, { method: "POST", form }),
  audio: (path, body) => request(path, { method: "POST", body, raw: true }),
};
