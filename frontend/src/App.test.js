/** Studio UI tests: sign-in gate, onboarding, goal intake and clarification. */
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import App from "./App";

const json = (data) => ({ ok: true, json: async () => data });
const persona = { key: "maya", name: "Maya Chen", title: "Senior Software Engineer", style: "Warm.", look: {}, voices: { browser: "female" } };
const config = {
  google_client_id: "",
  personas: [persona],
  pressures: [{ key: "realistic", description: "Typical" }],
  roles: [{ key: "software_engineering", label: "Software Engineering" }],
  levels: [{ key: "intern", label: "Intern" }],
  rounds: [{ key: "coding", label: "Coding", minutes: 45, assesses: "DSA" }],
  companies: [],
  competencies: {},
  server_keys: {},
};

function mockApi({ onboarded = true } = {}) {
  global.fetch = jest.fn(async (url, options = {}) => {
    const path = url.replace(/^https?:\/\/[^/]+/, "");
    if (path === "/studio/config") return json(config);
    if (path === "/studio/profile" && (!options.method || options.method === "GET")) return json({ prefs: { persona: "maya" }, target: {}, onboarding_done: onboarded, user: { id: "u1", name: "Ray Test", email: "r@example.com" } });
    if (path === "/studio/profile") return json({});
    if (path === "/settings/providers") return json({ providers: [{ key: "groq", chat: true, configured: true }] });
    if (path === "/studio/progress") return json({ completed: 0, focus: [], trend: [] });
    if (path === "/studio/interviews") return json({ interviews: [] });
    if (path === "/resume/status") return json({ has_resume: false });
    if (path === "/studio/intake/parse") return json({
      target: { company: "Google", company_key: "google", role_family: "software_engineering", employment: "", level: "" },
      missing: [{ field: "employment", question: "Is it an internship or a full-time position?", options: [{ value: "internship", label: "Internship" }, { value: "full_time", label: "Full-time" }] }],
    });
    throw new Error(`Unexpected request: ${path}`);
  });
}

beforeEach(() => {
  localStorage.clear();
  window.location.hash = "";
  window.scrollTo = jest.fn();
});

test("shows sign-up when signed out", async () => {
  mockApi();
  render(<App />);
  expect(await screen.findByRole("heading", { name: "Create your account" })).toBeInTheDocument();
});

test("first visit shows the welcome tour", async () => {
  localStorage.setItem("interviewer_token", "t");
  mockApi({ onboarded: false });
  render(<App />);
  expect(await screen.findByRole("dialog", { name: "Welcome tour" })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Skip" }));
  await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
});

test("goal text leads to a clarifying question", async () => {
  localStorage.setItem("interviewer_token", "t");
  mockApi();
  render(<App />);
  const box = await screen.findByLabelText("Describe the interview you're preparing for");
  fireEvent.change(box, { target: { value: "Google SWE interview" } });
  fireEvent.click(screen.getByRole("button", { name: /Continue/ }));
  expect(await screen.findByText("Is it an internship or a full-time position?")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Internship" })).toBeInTheDocument();
});
