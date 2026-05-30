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
# SIMPLE CACHE (REDIS-LIKE)
# =========================

CACHE = {}
CACHE_TTL = 300  # 5 minutes

def cache_get(key):
    entry = CACHE.get(key)
    if not entry:
        return None
    if time.time() - entry["time"] > CACHE_TTL:
        return None
    return entry["data"]

def cache_set(key, data):
    CACHE[key] = {"data": data, "time": time.time()}

# =========================
# CONFIG
# =========================

KEYWORDS = ["fund", "investment", "acquire", "close", "spv", "vehicle", "financing"]

RSS_FEEDS = [
    "https://www.privateequityinternational.com/feed/",
    "https://www.inframationnews.com/feed/"
]

# =========================
# UTIL
# =========================

def safe_time(dt):
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
# ENTITY EXTRACTION + NORMALISATION
# =========================

def normalize_entity(name):
    name = name.strip()

    cleanup = ["Partners", "Capital", "Group", "Holdings", "Management"]
    for c in cleanup:
        name = name.replace(c, "")

    return name.strip()

def extract_entity(text):
    try:
        matches = re.findall(r"\b(?:[A-Z][a-z]+(?:\s|$)){1,4}", text)
        candidates = [m.strip() for m in matches if len(m.strip()) > 2]

        for c in candidates:
            if any(x in c.lower() for x in ["capital", "partners", "equity", "ventures", "group"]):
                return normalize_entity(c)

        return normalize_entity(candidates[0]) if candidates else "Unknown"

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
    if "acquire" in t or "investment" in t:
        return "INVESTMENT"
    if "financing" in t:
        return "FINANCING"

    return "OTHER"

# =========================
# SOURCE: RSS (CACHED)
# =========================

def fetch_rss():
    cached = cache_get("rss")
    if cached:
        return cached

    out = []

    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)

            for e in feed.entries:
                try:
                    dt = datetime(*e.published_parsed[:6])
                except:
                    continue

                ts = safe_time(dt)

                if not is_recent(ts):
                    continue

                text = (e.title or "") + " " + (e.get("summary", "") or "")

                if not is_valid(text):
                    continue

                out.append({
                    "title": e.title,
                    "text": text,
                    "url": e.link,
                    "summary": e.get("summary", ""),
                    "source": "NEWS",
                    "timestamp": ts
                })

        except:
            continue

    cache_set("rss", out)
    return out

# =========================
# SOURCE: SEC EDGAR (SAFE)
# =========================

def fetch_sec():
    cached = cache_get("sec")
    if cached:
        return cached

    out = []

    try:
        r = requests.get(
            "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=5
        )

        soup = BeautifulSoup(r.text, "html.parser")

        for row in soup.find_all("tr")[:20]:
            text = row.get_text()

            if "D" not in text:
                continue

            if not is_valid(text):
                continue

            out.append({
                "title": text[:120],
                "text": text,
                "url": "https://www.sec.gov",
                "summary": "SEC Form D",
                "source": "SEC",
                "timestamp": safe_time(datetime.utcnow())
            })

    except:
        pass

    cache_set("sec", out)
    return out

# =========================
# SOURCE: PREQIN (SAFE)
# =========================

def fetch_preqin():
    cached = cache_get("preqin")
    if cached:
        return cached

    out = []

    try:
        r = requests.get("https://www.preqin.com/insights", timeout=5)

        soup = BeautifulSoup(r.text, "html.parser")

        for a in soup.find_all("a")[:15]:
            title = a.get_text(strip=True)

            if not title or not is_valid(title):
                continue

            out.append({
                "title": title,
                "text": title,
                "url": a.get("href") or "",
                "summary": "Preqin signal",
                "source": "PREQIN",
                "timestamp": safe_time(datetime.utcnow())
            })

    except:
        pass

    cache_set("preqin", out)
    return out

# =========================
# DEDUP: ENTITY + TEXT
# =========================

def dedupe(events):
    seen = set()
    out = []

    for e in events:
        key = (e.get("entity"), e.get("title", "")[:50])

        if key not in seen:
            seen.add(key)
            out.append(e)

    return out

# =========================
# ALERT ENGINE
# =========================

def assign_alert(g):
    if g["activity"]["last_6h"] >= 2:
        return "HIGH"
    if g["activity"]["last_24h"] >= 3:
        return "MEDIUM"
    if g["activity"]["last_48h"] >= 4:
        return "LOW"
    return None

# =========================
# GROUPING
# =========================

def group(events):
    g = {}
    now = datetime.utcnow()

    for e in events:
        ts = parse_iso(e["timestamp"])
        if not ts:
            continue

        entity = e["entity"]

        if entity not in g:
            g[entity] = {
                "entity": entity,
                "activity": {"last_6h":0,"last_24h":0,"last_48h":0},
                "activity_count":0,
                "events":[]
            }

        diff = now - ts

        if diff <= timedelta(hours=48):
            g[entity]["activity"]["last_48h"] += 1
        if diff <= timedelta(hours=24):
            g[entity]["activity"]["last_24h"] += 1
        if diff <= timedelta(hours=6):
            g[entity]["activity"]["last_6h"] += 1

        g[entity]["activity_count"] += 1
        g[entity]["events"].append(e)

    # add alerts
    for entity in g.values():
        entity["alert"] = assign_alert(entity)

    return sorted(
        g.values(),
        key=lambda x: (x["activity"]["last_6h"], x["activity"]["last_24h"]),
        reverse=True
    )

# =========================
# MAIN API
# =========================

@app.get("/events")
def get_events():

    try:
        raw = []
        raw += fetch_rss()
        raw += fetch_sec()
        raw += fetch_preqin()

        processed = []

        for e in raw:
            if not is_valid(e["text"]):
                continue

            processed.append({
                **e,
                "entity": extract_entity(e["text"]),
                "event_type": classify(e["text"])
            })

        processed = dedupe(processed)

        return group(processed)

    except Exception as e:
        print("ERROR:", e)
        return []
