"""End-to-end studio flow with a stubbed model: intake, interview turns, report, memory."""

import json
import os
import tempfile
import unittest
from unittest import mock

os.environ["AI_INTERVIEWER_DB"] = os.path.join(tempfile.mkdtemp(), "studio-test.db")
os.environ["GROQ_API_KEY"] = "test-key"
os.environ["STUDIO_NO_REFRESH"] = "1"

from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402
import memory  # noqa: E402


def fake_completion(provider, api_key, prompt, system="", json_mode=False, **kwargs):
    usage = {"prompt_tokens": len(prompt) // 4, "completion_tokens": 50, "cached_tokens": 0}
    if "turn a job seeker" in system:
        return json.dumps({"role_family": "software_engineering", "role_title": "Software Engineer", "level": "", "employment": "", "company": "Google", "rounds": [], "focus": "", "interview_date": ""}), usage
    if "interview researcher" in system:
        return json.dumps({"summary": "Two coding rounds and a Googleyness round.", "loop": [{"round": "coding", "focus": "DSA"}, {"round": "behavioral", "focus": "Googleyness"}], "look_for": ["Clear reasoning"], "tips": ["Practise graphs"], "confidence": "medium"}), usage
    if "realistic mock interview" in system:
        return json.dumps({
            "action": "next",
            "assessment": {"score": 3, "dimensions": {"communication": 3, "impact": 2}, "strengths": ["clear"], "missing": ["no metrics"], "evidence": "we shipped it"},
            "utterance": "",
            "notes": "Candidate gave a clear but metric-free intro.",
            "memory": [
                {"kind": "growth", "topic": "impact", "title": "No measurable results", "content": "Answers rarely quantify results or impact.", "confidence": 0.7},
                {"kind": "fact", "topic": "", "title": "Health", "content": "Candidate mentioned being diagnosed with anxiety disorder.", "confidence": 0.9},
            ],
        }), usage
    if "expert interview coach" in system:
        return json.dumps({"overall": {"readiness": "close", "headline": "Clear, but quantify impact.", "summary": "Good structure."}, "competencies": [{"key": "impact", "score": 2, "evidence": "no numbers", "next_step": "Add one metric per story"}], "questions": [{"number": 1, "what_worked": ["structure"], "what_was_missing": ["metrics"], "coach_questions": ["How would your manager measure that success?"], "better_outline": ["Situation", "Action", "Result with a number"], "sample_opening": "At my internship I cut build time by 40%."}], "patterns": ["Uses 'we' often"], "next_session": {"focus": ["impact"], "plan": "Practise metrics.", "drills": ["Rewrite one story with numbers"]}, "spoken_debrief": "Nice work today.", "memory": [{"kind": "story", "topic": "ownership", "title": "Build pipeline speedup", "content": "Internship story about speeding up the build pipeline.", "confidence": 0.8}]}), usage
    return json.dumps({"hint": "What would you clarify first?", "utterance": "Thanks for your question."}), usage


class StudioFlowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(main.app)
        res = cls.client.post("/auth/register", json={"email": "flow@example.com", "password": "secret123", "name": "Test User"})
        cls.headers = {"Authorization": f"Bearer {res.json()['token']}"}

    def test_full_flow(self):
        with mock.patch("llm.chat_completion", side_effect=fake_completion):
            config = self.client.get("/studio/config").json()
            self.assertEqual(len(config["personas"]), 4)

            parsed = self.client.post("/studio/intake/parse", json={"text": "Google SWE interview next month"}, headers=self.headers).json()
            self.assertEqual(parsed["target"]["company_key"], "google")
            fields = {q["field"] for q in parsed["missing"]}
            self.assertIn("employment", fields)

            answered = self.client.post("/studio/intake/answer", json={"target": parsed["target"], "answers": {"employment": "internship"}}, headers=self.headers).json()
            self.assertEqual(answered["target"]["level"], "intern")
            self.assertEqual(answered["missing"], [])
            target = answered["target"]

            brief = self.client.post("/studio/intake/brief", json={"target": target}, headers=self.headers).json()["brief"]
            self.assertTrue(brief["sources"])

            started = self.client.post("/studio/interviews", json={"target": target, "brief": brief, "minutes": 30, "persona": "priya"}, headers=self.headers).json()
            sid = started["session_id"]
            self.assertIn("Grace", started["utterance"])  # the old "priya" key maps to Grace
            self.assertGreaterEqual(started["total"], 2)

            first = self.client.post(f"/studio/interviews/{sid}/turn", json={"text": "I'm a CS student who built a scheduling app; we shipped it."}, headers=self.headers).json()
            self.assertEqual(first["action"], "next")
            self.assertEqual(first["index"], 1)
            self.assertTrue(first["utterance"])

            hint = self.client.post(f"/studio/interviews/{sid}/hint", headers=self.headers).json()
            self.assertTrue(hint["hint"])

            report = self.client.post(f"/studio/interviews/{sid}/finish", headers=self.headers).json()["report"]
            self.assertEqual(report["overall"]["readiness"], "close")
            self.assertEqual(report["questions"][0]["coach_questions"][0], "How would your manager measure that success?")

            retry = self.client.post(f"/studio/interviews/{sid}/retry", json={"number": 1, "answer": "I cut scheduling conflicts by 30% for 200 students."}, headers=self.headers)
            self.assertEqual(retry.status_code, 200)

            items = self.client.get("/studio/memory", headers=self.headers).json()["items"]
            contents = " ".join(i["content"] for i in items)
            self.assertIn("quantify", contents)
            self.assertNotIn("anxiety", contents)  # sensitive memory rejected
            self.assertIn("Build pipeline", " ".join(i["title"] for i in items))

            listing = self.client.get("/studio/interviews", headers=self.headers).json()["interviews"]
            self.assertEqual(listing[0]["status"], "completed")

            usage = self.client.get("/studio/account", headers=self.headers).json()["usage"]
            self.assertGreater(usage["calls"], 3)

    def test_memory_dedupe_and_review(self):
        user = self.client.get("/auth/me", headers=self.headers).json()
        uid = user["id"]
        memory.remember(uid, [{"kind": "growth", "topic": "trade_offs", "title": "Skips trade-offs", "content": "Rarely discusses trade-offs between design options.", "confidence": 0.6}])
        memory.remember(uid, [{"kind": "growth", "topic": "trade_offs", "title": "Skips trade-offs", "content": "Rarely discusses trade-offs between alternative design options.", "confidence": 0.6}])
        rows = [m for m in memory.list_memory(uid) if m["topic"] == "trade_offs"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["times_seen"], 2)
        self.assertEqual(rows[0]["status"], "active")
        for _ in range(3):
            memory.record_review(uid, "trade_offs", 4.5)
        rows = [m for m in memory.list_memory(uid) if m["topic"] == "trade_offs"]
        self.assertEqual(rows[0]["status"], "resolved")

    def test_question_bank_seeded(self):
        stats = self.client.get("/studio/questions/stats", headers=self.headers).json()
        total = sum(g["total"] for g in stats["groups"])
        self.assertGreater(total, 150)


if __name__ == "__main__":
    unittest.main()
