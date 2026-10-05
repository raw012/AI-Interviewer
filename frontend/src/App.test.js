import { fireEvent, render, screen, waitFor } from "@testing-library/react";
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
    if (url.endsWith("/settings/providers/groq/test")) return jsonResponse({ ok: true, message: "Connection successful" });
    if (url.endsWith("/settings/providers/groq/key")) return jsonResponse({ configured: true });
    if (url.endsWith("/settings/providers/active")) return jsonResponse({ llm_provider: "groq", transcription_provider: "groq" });
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
  expect(screen.getByRole("button", { name: "Connect interview intelligence" })).toBeEnabled();
  expect(screen.getByRole("button", { name: "Connect audio transcription" })).toBeEnabled();
  expect(screen.getByRole("button", { name: "Start interview" })).toBeDisabled();
  expect(screen.getAllByRole("button", { name: "Sign out" })).toHaveLength(1);
  expect(screen.queryByRole("button", { name: "Recordings" })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Profile" })).not.toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Connect interview intelligence" }));
  expect(await screen.findByRole("heading", { name: "API settings" })).toBeInTheDocument();
  expect(screen.getAllByRole("button", { name: "Sign out" })).toHaveLength(1);
});

test("hides onboarding and enables one-click Start with providers ready", async () => {
  mockAppRequests(true);
  render(<App />);

  await waitFor(() => expect(screen.getByRole("button", { name: "Start interview" })).toBeEnabled());
  expect(screen.queryByRole("heading", { name: "Connect your AI providers" })).not.toBeInTheDocument();
  expect(screen.queryByText(/Uses your last settings/i)).not.toBeInTheDocument();
  expect(screen.queryByRole("heading", { name: "Your recent interviews" })).not.toBeInTheDocument();
});

test("first-time API setup offers a key or Groq guidance", async () => {
  mockAppRequests(false);
  render(<App />);
  fireEvent.click((await screen.findAllByRole("button", { name: "API settings" }))[0]);
  expect(await screen.findByRole("button", { name: /I have an API key/i })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: /I need an API key/i }));
  expect(screen.getByRole("heading", { name: "Get a Groq API key" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: /Open Groq API Keys/i })).toHaveAttribute("href", "https://console.groq.com/keys");
  expect(screen.getByRole("button", { name: "Test & save key" })).toBeDisabled();
});

test("existing connection shows current provider instead of first-time choices", async () => {
  mockAppRequests(true);
  render(<App />);
  fireEvent.click((await screen.findAllByRole("button", { name: "API settings" }))[0]);
  expect(await screen.findByRole("heading", { name: "Ready for your next interview" })).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /I have an API key/i })).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Change connection" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Need a guide?" })).toBeInTheDocument();
});
