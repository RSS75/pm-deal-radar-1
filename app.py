from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import feedparser
import requests
import re
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import threading
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
# GLOBAL DATA STORE
# =========================

DATA_CACHE = []
LAST_UPDATED = None

# =========================
# CONFIG
# =========================

RSS_FEEDS = [
    "https://www.privateequityinternational.com/feed/",
    "https://www.inframationnews.com/feed/"
]

KEYWORDS = ["fund", "investment", "acquire", "close", "spv", "vehicle"]

# =========================
# UTIL
# =========================

def now_iso():
    return datetime.utcnow().isoformat()

def parse_iso(ts):
    try:
        return datetime.fromisoformat(ts)
    except:
        return None

def is_recent(dt):
    return dt and datetime.utcnow() - dt <= timedelta(hours=48)

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
# SAFE FETCH FUNCTIONS
# =========================

def fetch_rss():
    out = []
    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)

            for e in feed.entries[:10]:
                try:
                    dt = datetime(*e.published_parsed[:6])
                except:
                    continue

                if not is_recent(dt):
                    continue

                text = (e.title or "") + " " + (e.get("summary", "") or "")

                if not is_valid(text):
                    continue

                out.append({
                    "title": e.title,
                    "text": text,
                    "url": e.link,
                    "source": "NEWS",
                    "timestamp": dt.isoformat()
                })

        except:
            continue

    return out


def fetch_preqin():
    out = []
    try:
        r = requests.get(
            "https://www.preqin.com/insights",
            timeout=3,
            headers={"User-Agent": "Mozilla/5.0"}
        )

        soup = BeautifulSoup(r.text, "html.parser")

        for a in soup.find_all("a")[:10]:
            title = a.get_text(strip=True)

            if not title or not is_valid(title):
                continue

            out.append({
                "title": title,
                "text": title,
                "url": a.get("href") or "",
                "source": "PREQIN",
                "timestamp": now_iso()
            })

    except:
        pass

    return out


def fetch_sec():
    out = []

    try:
        r = requests.get(
            "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent",
            timeout=3,
            headers={"User-Agent": "Mozilla/5.0"}
        )

        soup = BeautifulSoup(r.text, "html.parser")

        for row in soup.find_all("tr")[:10]:
            text = row.get_text()

            if "D" not in text or not is_valid(text):
                continue

            out.append({
                "title": text[:100],
                "text": text,
                "url": "https://www.sec.gov",
                "source": "SEC",
                "timestamp": now_iso()
            })

    except:
        pass

    return out

# =========================
# PIPELINE (RUN IN BACKGROUND)
# =========================

def update_data():

    global DATA_CACHE, LAST_UPDATED

    while True:
        try:
            print("Refreshing data...")

            raw = []
            raw += fetch_rss()
            raw += fetch_preqin()
            raw += fetch_sec()

            processed = []

            for e in raw:
                entity = extract_entity(e["text"])
                event_type = classify(e["text"])

                processed.append({
                    **e,
                    "entity": entity,
                    "event_type": event_type
                })

            DATA_CACHE = processed
            LAST_UPDATED = now_iso()

            print("Update complete:", len(processed), "events")

        except Exception as e:
            print("Update error:", e)

        time.sleep(300)  # every 5 minutes

# =========================
# START BACKGROUND THREAD
# =========================

threading.Thread(target=update_data, daemon=True).start()

# =========================
# API
# =========================

@app.get("/")
def root():
    return {"status": "running", "last_updated": LAST_UPDATED}

@app.get("/events")
def get_events():
    return DATA_CACHE
``
