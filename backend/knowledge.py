"""Interview domain knowledge: roles, levels, round types and company formats.

Company formats summarise public candidate reports and official hiring pages.
They are guidance, not guarantees: loops vary by team, location and year, so
the product always shows the source type and asks the user to confirm.
"""

from __future__ import annotations

import re

ROLE_FAMILIES = {
    "software_engineering": {
        "label": "Software Engineering",
        "aliases": ["swe", "sde", "software engineer", "software developer", "backend", "full stack", "fullstack", "developer", "programmer", "engineer"],
    },
    "frontend_engineering": {
        "label": "Frontend Engineering",
        "aliases": ["frontend", "front-end", "front end", "web developer", "react", "ui engineer"],
    },
    "ml_engineering": {
        "label": "Machine Learning Engineering",
        "aliases": ["ml engineer", "machine learning", "mle", "ai engineer", "applied scientist", "research engineer", "llm", "deep learning"],
    },
    "data_science": {
        "label": "Data Science",
        "aliases": ["data scientist", "data science", "product analytics", "quantitative analyst", "statistician"],
    },
    "data_analytics": {
        "label": "Data Analytics",
        "aliases": ["data analyst", "business analyst", "analytics", "bi analyst", "business intelligence"],
    },
    "product_management": {
        "label": "Product Management",
        "aliases": ["product manager", "pm", "apm", "product owner", "tpm", "program manager"],
    },
}

LEVELS = {
    "intern": {
        "label": "Intern",
        "aliases": ["intern", "internship", "co-op", "coop", "summer"],
        "expectation": "Solid fundamentals and clear reasoning. Interviewers expect hints to be used well, working code for easy-to-medium problems, and honest, specific stories from school, projects or part-time work.",
    },
    "new_grad": {
        "label": "New grad / Entry",
        "aliases": ["new grad", "new graduate", "entry", "entry-level", "junior", "graduate", "l3", "e3", "sde i", "sde1", "sde-1", "ic1", "ic2"],
        "expectation": "Independent problem solving on medium problems with clean code and tested edge cases, basic design sense, and evidence of ownership on a project.",
    },
    "mid": {
        "label": "Mid-level",
        "aliases": ["mid", "mid-level", "intermediate", "l4", "e4", "sde ii", "sde2", "sde-2", "ic3"],
        "expectation": "Fluent coding under time pressure, sound system design for a well-scoped service, and examples where you drove a feature end to end and handled trade-offs.",
    },
    "senior": {
        "label": "Senior",
        "aliases": ["senior", "sr", "l5", "e5", "sde iii", "sde3", "ic4", "lead"],
        "expectation": "Leads the design conversation: clarifies scope, quantifies scale, defends trade-offs, and anticipates failure modes. Behavioral answers show influence across a team, mentoring and handling ambiguity.",
    },
    "staff": {
        "label": "Staff+",
        "aliases": ["staff", "principal", "l6", "e6", "l7", "e7", "architect", "ic5", "ic6"],
        "expectation": "Sets technical direction across teams, frames problems before solving them, reasons about organisational and long-term costs, and shows influence without authority at org scale.",
    },
}

ROUNDS = {
    "recruiter_screen": {"label": "Recruiter screen", "minutes": 20, "assesses": "Motivation, role fit, communication, logistics", "style": "conversational"},
    "behavioral": {"label": "Behavioral", "minutes": 45, "assesses": "Ownership, collaboration, conflict, ambiguity, impact, growth", "style": "STAR stories with specific personal actions and measurable results"},
    "coding": {"label": "Coding", "minutes": 45, "assesses": "Problem solving, data structures and algorithms, code quality, testing, communication", "style": "clarify, propose approach, analyse complexity, code, test"},
    "system_design": {"label": "System design", "minutes": 45, "assesses": "Requirements, high-level architecture, data model, scaling, trade-offs, reliability", "style": "requirements first, then high-level design, then deep dives"},
    "object_design": {"label": "Object-oriented design", "minutes": 45, "assesses": "Modelling, interfaces, extensibility, clean abstractions", "style": "clarify use cases, define classes and responsibilities, walk through flows"},
    "cs_fundamentals": {"label": "CS fundamentals", "minutes": 30, "assesses": "Operating systems, networking, databases, concurrency, language internals", "style": "explain concepts precisely with examples and trade-offs"},
    "frontend": {"label": "Frontend", "minutes": 45, "assesses": "JavaScript, browser internals, UI architecture, performance, accessibility", "style": "explain and build UI behaviour, reason about the browser"},
    "ml_fundamentals": {"label": "ML fundamentals", "minutes": 45, "assesses": "Learning theory, model choice, evaluation, debugging models", "style": "precise definitions, intuition, when and why"},
    "ml_system_design": {"label": "ML system design", "minutes": 45, "assesses": "Problem framing, data, features, model, evaluation, serving, monitoring", "style": "frame the ML problem, then the end-to-end pipeline and metrics"},
    "product_sense": {"label": "Product sense", "minutes": 45, "assesses": "User empathy, problem selection, solution design, prioritisation", "style": "goal, users, pain points, solutions, prioritise, metrics"},
    "product_execution": {"label": "Analytical / execution", "minutes": 45, "assesses": "Goals and metrics, diagnosing changes, trade-offs, decision making", "style": "define success, structure the diagnosis, decide with data"},
    "analytics_case": {"label": "Analytics case", "minutes": 45, "assesses": "Metric design, experiment design, diagnosing metric movements, product intuition", "style": "clarify, hypothesise, segment, quantify, recommend"},
    "statistics": {"label": "Statistics", "minutes": 30, "assesses": "Probability, inference, experimentation pitfalls", "style": "define, compute or estimate, interpret in plain language"},
    "sql": {"label": "SQL", "minutes": 30, "assesses": "Joins, aggregation, window functions, edge cases, readability", "style": "restate the table shape, write the query, check edge cases"},
    "resume_deep_dive": {"label": "Resume deep dive", "minutes": 30, "assesses": "Depth of ownership, technical decisions, impact, honesty about trade-offs", "style": "walk through a project; interviewer probes decisions"},
    "mixed": {"label": "Mixed loop", "minutes": 45, "assesses": "A cross-section of the role's main rounds", "style": "short segments across rounds"},
}

ROUND_ALIASES = {
    "recruiter_screen": ["recruiter", "phone screen", "hr screen", "screening call", "first call"],
    "behavioral": ["behavioral", "behavioural", "leadership principles", "googleyness", "culture fit", "hiring manager", "star", "soft skills"],
    "coding": ["coding", "leetcode", "algorithm", "algorithms", "data structures", "dsa", "technical screen", "oa", "online assessment", "live coding"],
    "system_design": ["system design", "architecture", "design round", "distributed systems", "scalability"],
    "object_design": ["object oriented design", "ood", "low level design", "lld", "class design"],
    "cs_fundamentals": ["operating systems", "os ", "networking", "computer networks", "databases", "fundamentals", "java oop", "oop", "concurrency"],
    "frontend": ["javascript", "react", "browser", "css", "frontend round"],
    "ml_fundamentals": ["ml fundamentals", "ml theory", "machine learning concepts", "ml breadth", "ml depth", "deep learning"],
    "ml_system_design": ["ml system design", "ml design", "recommendation system", "ranking system"],
    "product_sense": ["product sense", "product design", "design a product"],
    "product_execution": ["execution", "analytical thinking", "metrics", "product analytics round"],
    "analytics_case": ["case", "analytics case", "product case", "a/b test", "ab test", "experiment"],
    "statistics": ["statistics", "probability", "stats"],
    "sql": ["sql", "query", "queries"],
    "resume_deep_dive": ["resume", "project deep dive", "past projects", "experience deep dive"],
}

# Default round mix per role family when the user wants "the real loop".
DEFAULT_LOOPS = {
    "software_engineering": {
        "intern": ["coding", "coding", "behavioral"],
        "new_grad": ["coding", "coding", "behavioral", "object_design"],
        "mid": ["coding", "coding", "system_design", "behavioral"],
        "senior": ["coding", "system_design", "system_design", "behavioral"],
        "staff": ["system_design", "system_design", "behavioral", "coding"],
    },
    "frontend_engineering": {
        "intern": ["frontend", "coding", "behavioral"],
        "new_grad": ["frontend", "coding", "behavioral"],
        "mid": ["frontend", "coding", "system_design", "behavioral"],
        "senior": ["frontend", "system_design", "coding", "behavioral"],
        "staff": ["system_design", "frontend", "behavioral"],
    },
    "ml_engineering": {
        "intern": ["coding", "ml_fundamentals", "behavioral"],
        "new_grad": ["coding", "ml_fundamentals", "behavioral"],
        "mid": ["coding", "ml_fundamentals", "ml_system_design", "behavioral"],
        "senior": ["ml_system_design", "coding", "ml_fundamentals", "behavioral"],
        "staff": ["ml_system_design", "ml_system_design", "behavioral"],
    },
    "data_science": {
        "intern": ["sql", "statistics", "analytics_case", "behavioral"],
        "new_grad": ["sql", "analytics_case", "statistics", "behavioral"],
        "mid": ["analytics_case", "sql", "statistics", "behavioral"],
        "senior": ["analytics_case", "analytics_case", "sql", "behavioral"],
        "staff": ["analytics_case", "behavioral", "statistics"],
    },
    "data_analytics": {
        "intern": ["sql", "analytics_case", "behavioral"],
        "new_grad": ["sql", "analytics_case", "behavioral"],
        "mid": ["sql", "analytics_case", "behavioral"],
        "senior": ["analytics_case", "sql", "behavioral"],
        "staff": ["analytics_case", "behavioral"],
    },
    "product_management": {
        "intern": ["product_sense", "product_execution", "behavioral"],
        "new_grad": ["product_sense", "product_execution", "behavioral"],
        "mid": ["product_sense", "product_execution", "behavioral"],
        "senior": ["product_sense", "product_execution", "behavioral"],
        "staff": ["product_sense", "product_execution", "behavioral"],
    },
}

COMPANIES = {
    "google": {
        "label": "Google",
        "aliases": ["google", "alphabet", "deepmind", "youtube"],
        "summary": "Structured interviews scored independently and reviewed by a hiring committee. Technical rounds are typically 45 minutes; a Googleyness and leadership behavioral round is part of most loops. Intern loops are commonly reported as two technical interviews.",
        "values": ["Googleyness: curiosity, collaboration, user focus, comfort with ambiguity", "Emergent leadership, including in individual-contributor roles", "General cognitive ability and role-related knowledge"],
        "notes": {
            "software_engineering": "Commonly reported: phone screen, then 3-5 rounds of coding (medium to hard, often graph, tree, DP and design-a-data-structure problems), plus system design from mid-level up and a Googleyness round. Interns: usually two 45-minute technical interviews.",
            "product_management": "Product design (product sense), analytical/estimation, technical, and leadership rounds; the product round is often more open-ended with heavier probing.",
            "ml_engineering": "Coding, ML fundamentals or depth, resume deep dive, and ML system design for experienced levels.",
        },
        "sources": [
            {"label": "Bright Network – Google: how we hire", "url": "https://www.brightnetwork.co.uk/employer-advice/google/google-how-we-hire/", "kind": "official_mirror"},
            {"label": "igotanoffer – Googleyness & leadership questions", "url": "https://igotanoffer.com/blogs/tech/googleyness-leadership-interview-questions", "kind": "prep_guide"},
            {"label": "Taro – Google SWE intern experiences (2025)", "url": "https://www.jointaro.com/interviews/companies/google/experiences/software-engineering-intern-mountain-view-ca-may-22-2025-no-offer-neutral-7f5ed68c/", "kind": "candidate_reports"},
        ],
    },
    "meta": {
        "label": "Meta",
        "aliases": ["meta", "facebook", "instagram", "whatsapp", "fb"],
        "summary": "Recruiter call, a 45-minute technical screen, then a virtual onsite. Questions and themes are standardised, so patterns repeat. Candidates report two problems per 45-minute coding round.",
        "values": ["Move fast", "Focus on long-term impact", "Be direct and respect your colleagues", "Build awesome things"],
        "notes": {
            "software_engineering": "Commonly reported onsite: two coding rounds (often two medium problems in 45 minutes), one design round (system or product architecture; generally not at E3), and one behavioral round. Recent reports mention an AI-assisted coding round.",
            "data_science": "Product analytics loop: SQL, analytical reasoning and analytical execution case studies, and a behavioral round. The screen is commonly ~45 minutes split between SQL and product questions.",
            "product_management": "Product sense, analytical thinking (execution) and leadership & drive, each about 45 minutes.",
            "ml_engineering": "Coding (including an AI-assisted round), one or two ML system design rounds, and behavioral.",
        },
        "sources": [
            {"label": "Hello Interview – Meta E4 guide", "url": "https://www.hellointerview.com/guides/meta/e4", "kind": "prep_guide"},
            {"label": "Prepfully – Meta SWE guide", "url": "https://prepfully.com/interview-guides/meta-software-engineer", "kind": "prep_guide"},
            {"label": "Interview Query – Meta data scientist", "url": "https://www.interviewquery.com/interview-guides/Facebook-Data-Scientist", "kind": "prep_guide"},
            {"label": "Exponent – Meta PM interview", "url": "https://www.tryexponent.com/guides/meta-product-manager-interview", "kind": "prep_guide"},
        ],
    },
    "amazon": {
        "label": "Amazon",
        "aliases": ["amazon", "aws", "amazon web services"],
        "summary": "Every candidate is assessed against Amazon's Leadership Principles; each interviewer owns a few principles. Answers are expected in STAR form, in first person, with data. A Bar Raiser from outside the team joins the loop.",
        "values": ["Customer Obsession", "Ownership", "Invent and Simplify", "Are Right, A Lot", "Learn and Be Curious", "Hire and Develop the Best", "Insist on the Highest Standards", "Think Big", "Bias for Action", "Frugality", "Earn Trust", "Dive Deep", "Have Backbone; Disagree and Commit", "Deliver Results", "Strive to be Earth's Best Employer", "Success and Scale Bring Broad Responsibility"],
        "notes": {
            "software_engineering": "Online assessment (coding plus a work-style survey) for early-career roles, then 3-5 rounds of 45-60 minutes that combine a coding or design problem with Leadership Principle questions. System design from SDE II up.",
        },
        "sources": [
            {"label": "About Amazon – Leadership Principles interview", "url": "https://www.aboutamazon.com/news/workplace/amazon-leadership-principles-interview", "kind": "official"},
            {"label": "Amazon.jobs – in-person interview", "url": "https://amazon.jobs/en-gb/landing_pages/in-person-interview", "kind": "official"},
            {"label": "Simplify – Amazon SWE new grad guide", "url": "https://simplify.jobs/blog/amazon-swe-interview-new-grads", "kind": "prep_guide"},
        ],
    },
    "microsoft": {
        "label": "Microsoft",
        "aliases": ["microsoft", "msft", "azure", "linkedin"],
        "summary": "Commonly reported: a screen followed by 3-5 interviews mixing coding, design and behavioral questions, often with an 'as appropriate' interview with a senior leader.",
        "values": ["Growth mindset", "Customer obsession", "Collaboration across teams"],
        "notes": {
            "ml_engineering": "Reported 4-5 round onsite: coding, ML system design, ML depth and behavioral.",
        },
        "sources": [
            {"label": "Codemia – Microsoft MLE guide", "url": "https://codemia.io/guides/microsoft-machine-learning-engineer", "kind": "prep_guide"},
        ],
    },
    "apple": {
        "label": "Apple",
        "aliases": ["apple"],
        "summary": "Team-driven loops that vary widely by group. Candidates commonly report deep dives into past projects and domain specifics alongside coding.",
        "values": ["Attention to detail and craft", "Deep domain expertise", "Collaboration and secrecy-aware communication"],
        "notes": {},
        "sources": [],
    },
    "netflix": {
        "label": "Netflix",
        "aliases": ["netflix"],
        "summary": "Senior-leaning hiring with strong emphasis on culture (freedom and responsibility, candor). MLE loops are reported as ML system design, algorithmic coding and a behavioral discussion.",
        "values": ["Freedom and responsibility", "Candor and context, not control", "High performance"],
        "notes": {},
        "sources": [
            {"label": "Interview Query – Netflix MLE", "url": "https://www.interviewquery.com/interview-guides/netflix-machine-learning-engineer", "kind": "prep_guide"},
        ],
    },
    "nvidia": {"label": "NVIDIA", "aliases": ["nvidia"], "summary": "Team-specific technical loops; strong focus on fundamentals relevant to the team (systems, GPU, ML infrastructure).", "values": [], "notes": {}, "sources": []},
    "stripe": {"label": "Stripe", "aliases": ["stripe"], "summary": "Practical coding rounds on realistic problems (often working in a real codebase), integration and debugging exercises, plus design and behavioral.", "values": ["Users first", "Rigor", "Move with urgency and focus"], "notes": {}, "sources": []},
    "uber": {"label": "Uber", "aliases": ["uber"], "summary": "Coding, system design and behavioral rounds; design questions often relate to real-time, geo or marketplace systems.", "values": [], "notes": {}, "sources": []},
    "airbnb": {"label": "Airbnb", "aliases": ["airbnb"], "summary": "Coding, design and a strong values/culture interview.", "values": ["Champion the mission", "Be a host"], "notes": {}, "sources": []},
    "tiktok": {"label": "TikTok / ByteDance", "aliases": ["tiktok", "bytedance", "byte dance"], "summary": "Several coding-heavy rounds, often with follow-up variations, plus project deep dives.", "values": [], "notes": {}, "sources": []},
    "openai": {"label": "OpenAI", "aliases": ["openai"], "summary": "Practical coding and system design with emphasis on real-world engineering judgment; research and ML roles include deep project discussions.", "values": [], "notes": {}, "sources": []},
    "anthropic": {"label": "Anthropic", "aliases": ["anthropic"], "summary": "Practical coding and system design, with a focus on judgment, collaboration and mission alignment.", "values": [], "notes": {}, "sources": []},
}

# Interviewer personas: photo, default voices and conversational style.
# "kokoro" is the self-hosted default; "kokoro_alt" lists other voices that suit the same
# face (age and gender), so a user can change the voice without it clashing with the photo.
PERSONAS = {
    "maya": {
        "name": "Maya Chen",
        "title": "Software Engineer",
        "style": "Warm and precise. Gives the candidate room to think, then probes for specifics with calm, curious follow-ups.",
        "photo": "personas/maya.jpg",
        "voices": {"kokoro": "af_sarah", "kokoro_alt": ["af_heart"], "groq": "hannah", "elevenlabs": "EXAVITQu4vr4xnSDxMaL", "browser": "female"},
        "look": {"skin": "#F1C9A5", "skin_shade": "#D9A47E", "hair": "#1F1A1C", "hair_style": "long", "top": "#1F2230", "accent": "#7C8DB5", "glasses": False, "eyes": "#2B2422"},
    },
    "daniel": {
        "name": "Daniel Lin",
        "title": "Engineering Manager",
        "style": "Friendly, steady and direct. Listens closely and asks for concrete examples and what the candidate personally did.",
        "photo": "personas/daniel.jpg",
        "voices": {"kokoro": "am_liam", "kokoro_alt": ["am_puck"], "groq": "daniel", "elevenlabs": "JBFqnCBsd6RMkjVDRZzb", "browser": "male"},
        "look": {"skin": "#EBC3A0", "skin_shade": "#CFA07C", "hair": "#141012", "hair_style": "short", "top": "#1C2333", "accent": "#7FB3A2", "glasses": False, "eyes": "#1E1612"},
    },
    "grace": {
        "name": "Grace Liu",
        "title": "Staff Engineer",
        "style": "Direct and rigorous. Pushes on trade-offs, scale and failure modes, the way a bar-raising senior interviewer does.",
        "photo": "personas/grace.jpg",
        "voices": {"kokoro": "af_kore*0.7+zf_xiaoxiao*0.3@0.95", "kokoro_alt": ["af_kore@0.95", "bf_emma@0.95"], "groq": "diana", "elevenlabs": "9BWtsMINqrJLrRacOk9x", "browser": "female"},
        "look": {"skin": "#E9BE9A", "skin_shade": "#C99B77", "hair": "#1A1416", "hair_style": "long", "top": "#1B1B22", "accent": "#C89BC2", "glasses": True, "eyes": "#22170F"},
    },
    "david": {
        "name": "David Zhang",
        "title": "Engineering Director",
        "style": "Calm and big-picture. Asks about impact, decisions and trade-offs across teams, and how the candidate handles ambiguity.",
        "photo": "personas/david.jpg",
        "voices": {"kokoro": "am_michael*0.7+zm_yunjian*0.3@0.95", "kokoro_alt": ["am_michael@0.95", "am_fenrir@0.95"], "groq": "troy", "elevenlabs": "pNInz6obpgDQGcFmaJgB", "browser": "male"},
        "look": {"skin": "#E3B48E", "skin_shade": "#C2906B", "hair": "#5A5652", "hair_style": "short", "top": "#1D2433", "accent": "#E3B07A", "glasses": True, "eyes": "#2A1E16"},
    },
}

# Earlier persona keys still found in saved interviews and preferences.
PERSONA_ALIASES = {"priya": "grace", "alex": "david"}


def persona_key(key: str | None) -> str:
    """Map any stored persona key to a current one, defaulting to Maya."""
    key = PERSONA_ALIASES.get(key or "", key or "")
    return key if key in PERSONAS else "maya"


PRESSURE_STYLES = {
    "supportive": "Be encouraging. If the candidate is stuck for a while, offer a small nudge. Keep follow-ups gentle.",
    "realistic": "Behave like a typical professional interviewer at the target company: neutral-friendly, no hints unless the candidate is clearly stuck, follow up on vague parts.",
    "tough": "Behave like a demanding bar-raiser: neutral tone, press on vague claims, ask 'why' and 'what would you do differently', challenge assumptions. Stay respectful.",
}

VOICES = [
    {"id": "kokoro:af_sarah", "provider": "kokoro", "voice": "af_sarah", "label": "Sarah", "description": "Clear, professional (female) · on our server", "personas": ["maya"]},
    {"id": "kokoro:af_heart", "provider": "kokoro", "voice": "af_heart", "label": "Heart", "description": "Warm, natural (female) · on our server", "personas": ["maya"]},
    {"id": "kokoro:am_liam", "provider": "kokoro", "voice": "am_liam", "label": "Liam", "description": "Young, direct (male) · on our server", "personas": ["daniel"]},
    {"id": "kokoro:am_puck", "provider": "kokoro", "voice": "am_puck", "label": "Puck", "description": "Young, upbeat (male) · on our server", "personas": ["daniel"]},
    {"id": "kokoro:af_kore*0.7+zf_xiaoxiao*0.3@0.95", "provider": "kokoro", "voice": "af_kore*0.7+zf_xiaoxiao*0.3@0.95", "label": "Kore, light accent", "description": "Measured, slight accent (female) · on our server", "personas": ["grace"]},
    {"id": "kokoro:af_kore@0.95", "provider": "kokoro", "voice": "af_kore@0.95", "label": "Kore", "description": "Measured (female) · on our server", "personas": ["grace"]},
    {"id": "kokoro:bf_emma@0.95", "provider": "kokoro", "voice": "bf_emma@0.95", "label": "Emma", "description": "Crisp British (female) · on our server", "personas": ["grace"]},
    {"id": "kokoro:am_michael*0.7+zm_yunjian*0.3@0.95", "provider": "kokoro", "voice": "am_michael*0.7+zm_yunjian*0.3@0.95", "label": "Michael, light accent", "description": "Steady, slight accent (male) · on our server", "personas": ["david"]},
    {"id": "kokoro:am_michael@0.95", "provider": "kokoro", "voice": "am_michael@0.95", "label": "Michael", "description": "Warm, steady (male) · on our server", "personas": ["david"]},
    {"id": "kokoro:am_fenrir@0.95", "provider": "kokoro", "voice": "am_fenrir@0.95", "label": "Fenrir", "description": "Deep, serious (male) · on our server", "personas": ["david"]},
    {"id": "groq:hannah", "provider": "groq", "voice": "hannah", "label": "Hannah", "description": "Warm, clear (female)"},
    {"id": "groq:diana", "provider": "groq", "voice": "diana", "label": "Diana", "description": "Calm, confident (female)"},
    {"id": "groq:autumn", "provider": "groq", "voice": "autumn", "label": "Autumn", "description": "Bright, friendly (female)"},
    {"id": "groq:daniel", "provider": "groq", "voice": "daniel", "label": "Daniel", "description": "Steady, reassuring (male)"},
    {"id": "groq:austin", "provider": "groq", "voice": "austin", "label": "Austin", "description": "Upbeat, conversational (male)"},
    {"id": "groq:troy", "provider": "groq", "voice": "troy", "label": "Troy", "description": "Deep, measured (male)"},
    {"id": "elevenlabs:EXAVITQu4vr4xnSDxMaL", "provider": "elevenlabs", "voice": "EXAVITQu4vr4xnSDxMaL", "label": "Sarah", "description": "Soft, professional (female) · ElevenLabs"},
    {"id": "elevenlabs:9BWtsMINqrJLrRacOk9x", "provider": "elevenlabs", "voice": "9BWtsMINqrJLrRacOk9x", "label": "Aria", "description": "Expressive (female) · ElevenLabs"},
    {"id": "elevenlabs:JBFqnCBsd6RMkjVDRZzb", "provider": "elevenlabs", "voice": "JBFqnCBsd6RMkjVDRZzb", "label": "George", "description": "Warm British (male) · ElevenLabs"},
    {"id": "elevenlabs:pNInz6obpgDQGcFmaJgB", "provider": "elevenlabs", "voice": "pNInz6obpgDQGcFmaJgB", "label": "Adam", "description": "Deep, narrative (male) · ElevenLabs"},
    {"id": "browser", "provider": "browser", "voice": "", "label": "Device voice", "description": "Free, built into your browser; quality varies"},
]

COMPETENCY_LABELS = {
    "problem_solving": "Problem solving",
    "coding": "Coding & correctness",
    "communication": "Communication",
    "technical_depth": "Technical depth",
    "system_design": "System design",
    "trade_offs": "Trade-offs",
    "ownership": "Ownership",
    "collaboration": "Collaboration",
    "leadership": "Leadership & influence",
    "ambiguity": "Handling ambiguity",
    "customer_focus": "Customer focus",
    "impact": "Impact & results",
    "product_sense": "Product sense",
    "metrics": "Metrics & analytics",
    "experimentation": "Experimentation",
    "statistics": "Statistics",
    "sql": "SQL",
    "ml_knowledge": "ML knowledge",
    "ml_design": "ML system design",
    "learning": "Learning & growth",
    "structure": "Structured thinking",
}


def match_alias(text: str, table: dict, alias_key: str = "aliases") -> str | None:
    """Return the key whose alias appears in text (longest alias wins)."""
    lowered = f" {text.lower()} "
    best: tuple[int, str] | None = None
    for key, item in table.items():
        aliases = item.get(alias_key, []) if isinstance(item, dict) else item
        for alias in aliases:
            needle = alias.lower().strip()
            if needle and re.search(rf"(?<![a-z0-9]){re.escape(needle)}(?![a-z0-9])", lowered):
                if not best or len(needle) > best[0]:
                    best = (len(needle), key)
    return best[1] if best else None


def company_info(company: str) -> dict | None:
    if not company:
        return None
    key = company.lower().strip()
    if key in COMPANIES:
        return COMPANIES[key]
    found = match_alias(company, COMPANIES)
    return COMPANIES.get(found) if found else None


def company_key(company: str) -> str:
    if not company:
        return ""
    key = company.lower().strip()
    if key in COMPANIES:
        return key
    return match_alias(company, COMPANIES) or ""
