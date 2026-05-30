from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import feedparser
import requests
import json
import os
import re
from datetime import datetime, timedelta
import time

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# CONFIG
# =========================

DATA_FILE = "data.json"
UPDATE_INTERVAL = 300  # 5 minutes

RSS_FEEDS = [
    "https://www.privateequityinternational.com/feed/",
    "https://www.inframationnews.com/feed/"
]

COMPANIES_HOUSE_API_KEY = "YOUR_KEY"

KEYWORDS = ["fund", "investment", "acquire", "close", "spv"]

# =========================
# HELPERS
# =========================

def now():
    return time.time()

def is_valid(text):
    return text and any(k in text.lower() for k in KEYWORDS)

def extract_entity(text):
    try:
        matches = re.findall(r"\b(?:[A-Z][a-z]+(?:\s|$)){1,4}", text)
        return matches[0].strip() if matches else "Unknown"
    except:
        return "Unknown"

# =========================
# DATA FETCH (CONTROLLED)
# =========================

def fetch_data():
    raw = []

    # ✅ RSS (fast)
    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)

            for e in feed.entries[:5]:
                text = (e.title or "") + " " + (e.get("summary", "") or "")

                if not is_valid(text):
                    continue

                raw.append({
                    "title": e.title,
                    "text": text,
                    "url": e.link,
                    "source": "NEWS"
                })

        except:
            continue

    # ✅ Registry (very limited)
    try:
        r = requests.get(
            "https://api.company-information.service.gov.uk/search/companies?q=fund",
            timeout=2,
            auth=(COMPANIES_HOUSE_API_KEY, "")
        )

        if r.status_code == 200:
            items = r.json().get("items", [])

            for i in items[:3]:
                title = i.get("title", "")

                if not is_valid(title):
                    continue

                raw.append({
                    "title": f"Registry: {title}",
                    "text": title,
                    "url": "https://find-and-update.company-information.service.gov.uk/company/" + i.get("company_number", ""),
                    "source": "REGISTRY"
                })

    except:
        pass

    # ✅ GROUP
    grouped = {}

    for e in raw:
        entity = extract_entity(e["text"])

        if entity not in grouped:
            grouped[entity] = {
                "entity": entity,
                "events": [],
                "activity_count": 0
            }

        grouped[entity]["events"].append(e)
        grouped[entity]["activity_count"] += 1

    return list(grouped.values())

# =========================
# FILE CACHE LOGIC
# =========================

def needs_update():
    if not os.path.exists(DATA_FILE):
        return True

    last_modified = os.path.getmtime(DATA_FILE)
    return now() - last_modified > UPDATE_INTERVAL

def get_data():

    # ✅ update if needed
    if needs_update():
        try:
            data = fetch_data()

            with open(DATA_FILE, "w") as f:
                json.dump(data, f)

        except:
            pass  # silently fail

    # ✅ serve existing data
    try:
        with open(DATA_FILE) as f:
            return json.load(f)
    except:
        return []

# =========================
# API
# =========================

@app.get("/")
def root():
    return {"status": "running"}

@app.get("/events")
def events():
    return get_data()
