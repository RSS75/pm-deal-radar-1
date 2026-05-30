from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import feedparser
import requests
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
CACHE_TTL = 300  # 5 minutes

REGISTRY_CACHE = {"data": [], "timestamp": 0}
REGISTRY_TTL = 60  # 1 minute

# =========================
# CONFIG
# =========================

RSS_FEEDS = [
    "https://www.privateequityinternational.com/feed/",
    "https://www.inframationnews.com/feed/"
]

COMPANIES_HOUSE_API_KEY = "YOUR_KEY_HERE"

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
# ENTITY EXTRACTION
# =========================

def extract_entity(text):
    try:
        matches = re.findall(r"\b(?:[A-Z][a-z]+(?:\s|$)){1,4}", text)
        return matches[0].strip() if matches else "Unknown"
    except:
        return "Unknown"

# =========================
# CLASSIFICATION
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
# SAFE FETCH WRAPPER
# =========================

def safe_fetch(fn):
    try:
        return fn()
    except Exception as e:
        print(f"{fn.__name__} failed:", e)
        return []

# =========================
# SOURCE 1: RSS (CORE)
# =========================

def fetch_rss():
    out = []

    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)

            for e in feed.entries[:5]:  # very limited

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
# SOURCE 2: REGISTRY (SAFE + LIMITED)
# =========================

def fetch_registry():
    out = []

    try:
        r = requests.get(
            "https://api.company-information.service.gov.uk/search/companies?q=fund",
            timeout=2,
            auth=(COMPANIES_HOUSE_API_KEY, "")
        )

        if r.status_code != 200:
            return []

        items = r.json().get("items", [])

        for i in items[:3]:  # very limited
            title = i.get("title", "")

            if not is_valid(title):
                continue

            out.append({
                "title": f"Registry: {title}",
                "text": title,
                "url": f"https://find-and-update.company-information.service.gov.uk/company/{i.get('company_number')}",
                "source": "REGISTRY",
                "timestamp": safe_iso(datetime.utcnow())
            })

    except:
        pass

    return out

# =========================
# REGISTRY CACHE CONTROL
# =========================

def get_registry_data():
    global REGISTRY_CACHE

    if now() - REGISTRY_CACHE["timestamp"] < REGISTRY_TTL:
        return REGISTRY_CACHE["data"]

    data = safe_fetch(fetch_registry)

    REGISTRY_CACHE["data"] = data
    REGISTRY_CACHE["timestamp"] = now()

    return data

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
# MAIN PIPELINE
# =========================

def refresh_data():
    raw = []

    raw += safe_fetch(fetch_rss)          # fast
    raw += get_registry_data()            # throttled (1/min)

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

@app.get("/")
def root():
    return {"status": "running"}

@app.get("/events")
def get_events():

    try:
        if now() - CACHE["timestamp"] < CACHE_TTL:
            return CACHE["data"]

        data = refresh_data()

        CACHE["data"] = data
        CACHE["timestamp"] = now()

        return data

    except Exception as e:
        print("CRITICAL ERROR:", e)
        return CACHE["data"]
