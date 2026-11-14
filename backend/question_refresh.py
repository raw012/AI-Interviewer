"""Refresh "recently asked" signals for coding problems.

Pulls the public, candidate-reported company lists (30-day window) from
github.com/liquidslr/leetcode-company-wise-problems and stores, per company,
which problem patterns were reported recently and how often. The planner uses
this to prioritise runnable problems for the target company; the intake brief
shows the trending topics. Only titles, difficulty, frequency and topic tags
are stored; problem statements are never copied.

Run weekly:  cd backend && python question_refresh.py
(cron example: 0 6 * * 1 cd /path/to/backend && ./venv/bin/python question_refresh.py)
The API also runs it in the background at startup when data is over 7 days old.
"""

from __future__ import annotations

import csv
import io
import re
import threading
from urllib.parse import quote

import httpx

from studio_store import save_trending, trending_age_days

REPO = "liquidslr/leetcode-company-wise-problems"
SOURCE = f"https://github.com/{REPO}"
RAW = f"https://raw.githubusercontent.com/{REPO}/main"
WINDOWS = [("1. Thirty Days.csv", "30d"), ("2. Three Months.csv", "90d")]
# our company key -> folder name in the source repository
COMPANY_FOLDERS = {
    "google": "Google", "meta": "Meta", "amazon": "Amazon", "microsoft": "Microsoft", "apple": "Apple",
    "netflix": "Netflix", "nvidia": "Nvidia", "stripe": "Stripe", "uber": "Uber", "airbnb": "Airbnb",
    "tiktok": "TikTok", "openai": "OpenAI", "anthropic": "Anthropic",
}
MIN_ROWS = 8  # fall back to the 90-day window when the 30-day list is thin


def slug(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")


def _fetch(folder: str, filename: str) -> list[dict]:
    response = httpx.get(f"{RAW}/{quote(folder)}/{quote(filename)}", timeout=20, follow_redirects=True)
    if response.status_code != 200:
        return []
    rows = []
    for row in csv.DictReader(io.StringIO(response.text)):
        title = (row.get("Title") or "").strip()
        if not title:
            continue
        link = (row.get("Link") or "").rstrip("/")
        try:
            frequency = float(row.get("Frequency") or 0)
        except ValueError:
            frequency = 0
        rows.append({
            "ref": link.rsplit("/", 1)[-1] if "/problems/" in link else slug(title),
            "title": title,
            "difficulty": (row.get("Difficulty") or "").strip(),
            "frequency": frequency,
            "topics": (row.get("Topics") or "").strip(),
        })
    return rows


def refresh(companies: dict[str, str] | None = None) -> dict[str, int]:
    result = {}
    for key, folder in (companies or COMPANY_FOLDERS).items():
        try:
            rows, window = [], "30d"
            for filename, label in WINDOWS:
                rows, window = _fetch(folder, filename), label
                if len(rows) >= MIN_ROWS:
                    break
            if rows:
                for row in rows:
                    row["window"] = window
                result[key] = save_trending(key, rows, SOURCE)
        except Exception:
            continue  # one company failing must not stop the rest
    return result


def refresh_if_stale(max_age_days: float = 7) -> None:
    """Non-blocking refresh used at API startup."""
    try:
        age = trending_age_days()
    except Exception:
        return
    if age is not None and age < max_age_days:
        return
    threading.Thread(target=refresh, daemon=True).start()


if __name__ == "__main__":
    from storage import init_db

    init_db()
    for company, count in refresh().items():
        print(f"{company}: {count} recently reported problems")
