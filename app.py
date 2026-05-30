from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import feedparser
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
# CACHE
# =========================

CACHE = {"data": [], "timestamp": 0}
CACHE_TTL = 300  # 5 min

# =========================
# CONFIG
# =========================

RSS_FEEDS = [
    "https://www.privateequityinternational.com/feed/",
    "https://www.inframationnews.com/feed/"
]

KEYWORDS = ["fund", "investment", "acquire", "close", "spv"]

# =========================
# HELPERS
# =========================

def now():
    return time.time()

def safe_iso(dt):
    try:
        return dt.isoformat()
    except:
        return datetime.utcnow().isoformat()

def parse_iso(ts):
    try:
        return datetime.fromisoformat(ts)
    except:
        return None

def is_recent(ts):
    dt = parse_iso(ts)
    return dt and (datetime.utcnow() - dt <= timedelta(hours=48))

def is_valid(text):
    return text and any(k in text.lower() for k in KEYWORDS)

# =========================
# ENTITY
# =========================

def extract_entity(text):
    try:
        matches = re.findall(r"\b(?:[A-Z][a-z]+(?:\s|$)){1,4}", text)
        return matches[0].strip() if matches else "Unknown"
    except:
        return "Unknown"

# =========================
# CLASSIFY
# =========================

def classify(text):
    t = text.lower()

    if "fund" in t and ("launch" in t or "raise" in t):
        return "FUND_LAUNCH"
    if "close" in t:
        return "FUND_CLOSE"
    if "spv" in t:
        return "STRUCTURE"
    if "investment" in t:
        return "INVESTMENT"

    return "OTHER"

# =========================
# RSS ONLY (SAFE)
# =========================

def fetch_rss():
    out = []

    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)

            # 🔥 VERY small sample (critical)
            for e in feed.entries[:5]:

                try:
                    dt = datetime(*e.published_parsed[:6])
                except:
                    continue

                ts = safe_iso(dt)

                if not is_recent(ts):
                    continue

                text = (e.title or "") + " " + (e.get("summary", "") or "")

                if not is_valid(text):
                    continue

                out.append({
                    "title": e.title,
                    "text": text,
                    "url": e.link,
                    "source": "NEWS",
                    "timestamp": ts
                })

        except:
            continue

    return out

# =========================
# GROUP
# =========================

def group(events):
    grouped = {}

    for e in events:
        entity = e["entity"]

        if entity not in grouped:
            grouped[entity] = {
                "entity": entity,
                "activity_count": 0,
                "events": []
            }

        grouped[entity]["events"].append(e)
        grouped[entity]["activity_count"] += 1

    return list(grouped.values())

# =========================
# MAIN
# =========================

def refresh_data():
    raw = fetch_rss()

    processed = []

    for e in raw:
        if not is_valid(e["text"]):
            continue

        processed.append({
            **e,
            "entity": extract_entity(e["text"]),
            "event_type": classify(e["text"])
        })

    return group(processed)

# =========================
# API
# =========================

@app.get("/events")
def get_events():
    try:
        # ✅ cache hit
        if now() - CACHE["timestamp"] < CACHE_TTL:
            return CACHE["data"]

        # ✅ refresh (LIGHT)
        data = refresh_data()

        CACHE["data"] = data
        CACHE["timestamp"] = now()

        return data

    except:
        return CACHE["data"]
