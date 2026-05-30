from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import feedparser
import requests
import re
from bs4 import BeautifulSoup
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
# CACHE (ABSOLUTE KEY FIX)
# =========================

CACHE = {"data": [], "timestamp": 0}
CACHE_TTL = 300  # 5 mins

# =========================
# CONFIG
# =========================

RSS_FEEDS = [
    "https://www.privateequityinternational.com/feed/",
    "https://www.inframationnews.com/feed/"
]

KEYWORDS = ["fund", "investment", "acquire", "close", "spv", "vehicle"]

# =========================
# SAFE HELPERS
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
# SAFE FETCH WRAPPER
# =========================

def safe_fetch(fn):
    try:
        return fn()
    except Exception as e:
        print(f"{fn.__name__} failed:", e)
        return []

# =========================
# SOURCES (LIGHTWEIGHT)
# =========================

def fetch_rss():
    out = []

    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)

            for e in feed.entries[:8]:  # VERY IMPORTANT (reduced load)

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


def fetch_preqin():
    out = []

    try:
        r = requests.get(
            "https://www.preqin.com/insights",
            timeout=2,
            headers={"User-Agent": "Mozilla/5.0"}
        )

        soup = BeautifulSoup(r.text, "html.parser")

        for a in soup.find_all("a")[:6]:  # 🔥 reduced

            title = a.get_text(strip=True)

            if not title or not is_valid(title):
                continue

            out.append({
                "title": title,
                "text": title,
                "url": a.get("href") or "",
                "source": "PREQIN",
                "timestamp": safe_iso(datetime.utcnow())
            })

    except:
        pass

    return out


def fetch_sec():
    out = []

    try:
        r = requests.get(
            "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent",
            timeout=2,
            headers={"User-Agent": "Mozilla/5.0"}
        )

        soup = BeautifulSoup(r.text, "html.parser")

        for row in soup.find_all("tr")[:6]:  # 🔥 reduced

            text = row.get_text()

            if "D" not in text or not is_valid(text):
                continue

            out.append({
                "title": text[:100],
                "text": text,
                "url": "https://www.sec.gov",
                "source": "SEC",
                "timestamp": safe_iso(datetime.utcnow())
            })

    except:
        pass

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
                "events": []
            }

        grouped[entity]["events"].append(e)

    return list(grouped.values())

# =========================
# MAIN FETCH (ONLY WHEN NEEDED)
# =========================

def refresh_data():

    raw = []
    raw += safe_fetch(fetch_rss)
    raw += safe_fetch(fetch_preqin)
    raw += safe_fetch(fetch_sec)

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
        # ✅ CACHE CHECK
        if now() - CACHE["timestamp"] < CACHE_TTL:
            return CACHE["data"]

        # ✅ FETCH NEW DATA
        data = refresh_data()

        CACHE["data"] = data
        CACHE["timestamp"] = now()

        return data

    except Exception as e:
        print("CRITICAL ERROR:", e)
        return CACHE["data"]  # fallback
