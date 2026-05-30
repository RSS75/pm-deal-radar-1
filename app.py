from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import feedparser
import re
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
# SOURCES (REAL ONLY)
# =========================

RSS_FEEDS = [
    "https://www.privateequityinternational.com/feed/",
    "https://www.inframationnews.com/feed/"
]

# =========================
# TIME FILTER (48 HOURS)
# =========================

def is_recent(entry):
    try:
        published = entry.get("published_parsed")

        if not published:
            return True  # fallback

        published_dt = datetime(*published[:6])
        now = datetime.utcnow()

        return (now - published_dt) <= timedelta(hours=48)

    except:
        return True  # safe fallback


# =========================
# SOURCE LAYER
# =========================

def fetch_rss():
    data = []

    for url in RSS_FEEDS:
        feed = feedparser.parse(url)

        for e in feed.entries:

            # ✅ 48H FILTER HERE (BACKEND LEVEL ✅)
            if not is_recent(e):
                continue

            data.append({
                "title": e.title,
                "text": f"{e.title} {e.get('summary','')}",
                "url": e.link,
                "source": "NEWS",
                "summary": e.get("summary", ""),
                "timestamp": datetime(*e.published_parsed[:6]).isoformat()
                if "published_parsed" in e else None
            })

    return data


# =========================
# INTELLIGENCE ENGINE
# =========================

def is_real_deal(text):
    DEAL_TERMS = ["acquire", "investment", "fund", "close", "financing", "stake", "launch", "spv"]
    NOISE = ["opinion", "analysis", "how", "why"]

    t = text.lower()
    return any(k in t for k in DEAL_TERMS) and not any(n in t for n in NOISE)


def is_illiquid_gp(text):
    GP_TERMS = ["capital", "partners", "equity", "infrastructure", "real estate", "ventures"]
    EXCLUDE = ["bank", "etf", "insurance"]

    t = text.lower()
    return any(k in t for k in GP_TERMS) and not any(e in t for e in EXCLUDE)


def classify(text):
    t = text.lower()

    if "fund" in t and ("close" in t or "launch" in t or "raising" in t):
        return "FUND"

    if "acquire" in t or "investment" in t or "stake" in t:
        return "INVESTMENT"

    if "debt" in t or "financing" in t:
        return "FINANCING"

    if "spv" in t or "vehicle" in t:
        return "STRUCTURE"

    return "OTHER"


def detect_region(text):
    t = text.lower()

    if re.search(r"india|china|japan|asia", t):
        return "ASIA"
    if re.search(r"germany|france|spain|europe", t):
        return "EUROPE"
    if re.search(r"uk|britain", t):
        return "UK"
    if re.search(r"us|america", t):
        return "US"

    return "GLOBAL"


# =========================
# EXPOSURE ENGINE
# =========================

def infer_exposure(text, region, event_type):
    cross_border = region != "US"
    leverage = "debt" in text.lower() or event_type == "FINANCING"

    return {
        "fx": cross_border,
        "ir": leverage
    }


# =========================
# PRIORITY
# =========================

def score(event):
    score = 0

    if event["fx"]:
        score += 3

    if event["ir"]:
        score += 2

    if event["event_type"] in ["FUND", "INVESTMENT"]:
        score += 2

    return score


# =========================
# MAIN API
# =========================

@app.get("/")
def root():
    return {"status": "running"}


@app.get("/events")
def get_events():

    raw = fetch_rss()  # ✅ ONLY REAL DATA NOW

    processed = []

    for r in raw:
        text = r["text"]

        if not is_real_deal(text):
            continue

        if not is_illiquid_gp(text):
            continue

        event_type = classify(text)
        region = detect_region(text)
        exposure = infer_exposure(text, region, event_type)

        event = {
            **r,
            "region": region,
            "event_type": event_type,
            "fx": exposure["fx"],
            "ir": exposure["ir"],
            "priority": score({
                "fx": exposure["fx"],
                "ir": exposure["ir"],
                "event_type": event_type
            })
        }

        processed.append(event)

    return sorted(processed, key=lambda x: x["priority"], reverse=True)
``
