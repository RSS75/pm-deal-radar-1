from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import feedparser
import requests
import re
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

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

RSS_FEEDS = [
    "https://www.privateequityinternational.com/feed/",
    "https://www.inframationnews.com/feed/"
]

COMPANIES_HOUSE_API_KEY = "ADD_YOUR_KEY_HERE"

KEYWORDS = ["fund", "investment", "acquire", "close", "spv", "vehicle", "financing"]

# =========================
# TIME FILTER (48H)
# =========================

def is_recent(dt):
    return dt and (datetime.utcnow() - dt <= timedelta(hours=48))

# =========================
# ✅ DYNAMIC ENTITY EXTRACTION (FIXED)
# =========================

def extract_entity(text):
    """
    Dynamically extract GP / firm names (no hardcoding)
    """

    # Step 1: extract candidate capitalised phrases
    matches = re.findall(r"\b(?:[A-Z][a-z]+(?:\s|$)){1,4}", text)

    candidates = [m.strip() for m in matches if len(m.strip()) > 2]

    # Step 2: filter for GP-like names
    GP_HINTS = [
        "capital", "partners", "equity", "ventures",
        "infrastructure", "real estate", "management", "group", "holdings"
    ]

    for c in candidates:
        if any(h in c.lower() for h in GP_HINTS):
            return c

    # Step 3: fallback
    return candidates[0] if candidates else "Unknown"

# =========================
# CLASSIFICATION
# =========================

def classify(text):
    t = text.lower()

    if "fund" in t and ("launch" in t or "raise" in t):
        return "FUND_LAUNCH"

    if "close" in t:
        return "FUND_CLOSE"

    if "spv" in t or "vehicle" in t:
        return "STRUCTURE"

    if "acquire" in t or "investment" in t:
        return "INVESTMENT"

    if "debt" in t or "financing" in t:
        return "FINANCING"

    return "OTHER"

def is_valid(text):
    return any(k in text.lower() for k in KEYWORDS)

# =========================
# SOURCE 1: RSS
# =========================

def fetch_rss():
    results = []

    for url in RSS_FEEDS:
        feed = feedparser.parse(url)

        for e in feed.entries:
            if not e.get("published_parsed"):
                continue

            dt = datetime(*e.published_parsed[:6])

            if not is_recent(dt):
                continue

            text = e.title + " " + e.get("summary", "")

            if not is_valid(text):
                continue

            results.append({
                "title": e.title,
                "text": text,
                "url": e.link,
                "summary": e.get("summary", ""),
                "source": "NEWS",
                "timestamp": dt.isoformat()
            })

    return results

# =========================
# SOURCE 2: REGISTRY (UK)
# =========================

def fetch_registry():
    results = []

    try:
        url = "https://api.company-information.service.gov.uk/search/companies?q=fund"

        r = requests.get(
            url,
            auth=(COMPANIES_HOUSE_API_KEY, ""),
            timeout=5
        )

        data = r.json()

        for item in data.get("items", [])[:15]:
            title = item.get("title", "")

            if not is_valid(title):
                continue

            results.append({
                "title": f"New entity registered: {title}",
                "text": title,
                "url": f"https://find-and-update.company-information.service.gov.uk/company/{item.get('company_number')}",
                "summary": "Registry signal: potential fund/SPV",
                "source": "REGISTRY",
                "timestamp": datetime.utcnow().isoformat()
            })

    except Exception as e:
        print("Registry error:", e)

    return results

# =========================
# SOURCE 3: PREQIN
# =========================

def fetch_preqin():
    results = []

    try:
        url = "https://www.preqin.com/insights"
        r = requests.get(url, timeout=5)

        soup = BeautifulSoup(r.text, "html.parser")

        links = soup.find_all("a")

        for a in links[:30]:
            title = a.get_text(strip=True)

            if not title or not is_valid(title):
                continue

            results.append({
                "title": title,
                "text": title,
                "url": a.get("href"),
                "summary": "Preqin signal",
                "source": "PREQIN",
                "timestamp": datetime.utcnow().isoformat()
            })

    except Exception as e:
        print("Preqin error:", e)

    return results

# =========================
# DEDUPLICATION
# =========================

def deduplicate(events):
    seen = set()
    clean = []

    for e in events:
        key = e["title"]

        if key not in seen:
            seen.add(key)
            clean.append(e)

    return clean

# =========================
# ✅ GROUP BY ENTITY + TIME CLUSTERING
# =========================

def group_by_entity(events):
    grouped = {}
    now = datetime.utcnow()

    for e in events:
        entity = e["entity"]
        ts = datetime.fromisoformat(e["timestamp"])

        if entity not in grouped:
            grouped[entity] = {
                "entity": entity,
                "activity_count": 0,
                "activity": {
                    "last_6h": 0,
                    "last_24h": 0,
                    "last_48h": 0
                },
                "events": []
            }

        grouped[entity]["events"].append(e)
        grouped[entity]["activity_count"] += 1

        diff = now - ts

        if diff <= timedelta(hours=48):
            grouped[entity]["activity"]["last_48h"] += 1
        if diff <= timedelta(hours=24):
            grouped[entity]["activity"]["last_24h"] += 1
        if diff <= timedelta(hours=6):
            grouped[entity]["activity"]["last_6h"] += 1

    # sort events per entity by most recent
    for g in grouped.values():
        g["events"].sort(key=lambda x: x["timestamp"], reverse=True)

    # sort entities by activity intensity
    return sorted(
        grouped.values(),
        key=lambda x: (
            x["activity"]["last_6h"],
            x["activity"]["last_24h"],
            x["activity"]["last_48h"]
        ),
        reverse=True
    )

# =========================
# MAIN API
# =========================

@app.get("/")
def root():
    return {"status": "running"}

@app.get("/events")
def get_events():

    raw = []
    raw += fetch_rss()
    raw += fetch_registry()
    raw += fetch_preqin()

    raw = deduplicate(raw)

    processed = []

    for e in raw:
        if not is_valid(e["text"]):
            continue

        entity = extract_entity(e["text"])
        event_type = classify(e["text"])

        processed.append({
            **e,
            "entity": entity,
            "event_type": event_type
        })

    return group_by_entity(processed)
