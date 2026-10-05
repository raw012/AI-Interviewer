import { render, screen, waitFor } from "@testing-library/react";
import App from "./App";

const jsonResponse = (data) => ({ ok: true, json: async () => data });

function mockAppRequests(connected) {
  const provider = {
    key: "groq",
    name: "Groq",
    chat: true,
    transcription: true,
    model: "preview-model",
    configured: connected,
    server_fallback_available: false,
  };
  global.fetch = jest.fn(async (url) => {
    if (url.endsWith("/auth/me")) return jsonResponse({ id: "preview-user", name: "Preview User" });
    if (url.endsWith("/topics")) return jsonResponse({ topics: [] });
    if (url.endsWith("/resume/status")) return jsonResponse({ has_resume: true, filename: "resume.pdf" });
    if (url.endsWith("/dashboard")) return jsonResponse({ interviews: [], summary: { interviews: 0 } });
    if (url.endsWith("/settings/providers")) return jsonResponse({ providers: [provider], llm_provider: "groq", transcription_provider: "groq" });
    throw new Error(`Unexpected request: ${url}`);
  });
}

beforeEach(() => {
  localStorage.clear();
  localStorage.setItem("interviewer_token", "preview-token");
});

afterEach(() => {
  jest.restoreAllMocks();
});

test("makes provider setup primary and disables Start without keys", async () => {
  mockAppRequests(false);
  render(<App />);

  expect(await screen.findByRole("heading", { name: "Connect your AI providers" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Connect providers" })).toBeEnabled();
  expect(screen.getByRole("button", { name: "Start interview" })).toBeDisabled();
  expect(screen.queryByRole("button", { name: "Recordings" })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Profile" })).not.toBeInTheDocument();
});

test("hides onboarding and enables one-click Start with providers ready", async () => {
  mockAppRequests(true);
  render(<App />);

  await waitFor(() => expect(screen.getByRole("button", { name: "Start interview" })).toBeEnabled());
  expect(screen.queryByRole("heading", { name: "Connect your AI providers" })).not.toBeInTheDocument();
  expect(screen.queryByText(/Uses your last settings/i)).not.toBeInTheDocument();
});
