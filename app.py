from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import feedparser
import re

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# SOURCES
# =========================

RSS_FEEDS = [
    "https://www.privateequityinternational.com/feed/",
    "https://www.inframationnews.com/feed/"
]

# =========================
# SOURCE LAYER
# =========================

def fetch_rss():
    data = []

    for url in RSS_FEEDS:
        feed = feedparser.parse(url)

        for e in feed.entries[:20]:
            data.append({
                "title": e.title,
                "text": f"{e.title} {e.get('summary','')}",
                "url": e.link,
                "source": "NEWS"
            })

    return data


def fetch_registries():
    # ✅ placeholder for Companies House / SEC later
    return [
        {
            "title": "SPV created for infrastructure investment",
            "text": "New SPV infrastructure fund Europe created",
            "url": "#",
            "source": "REGISTRY"
        }
    ]


def fetch_social():
    # ✅ lightweight signal layer (not scraping LinkedIn)
    return [
        {
            "title": "KKR launches new infrastructure fund",
            "text": "KKR infrastructure fund Europe launch",
            "url": "#",
            "source": "SOCIAL"
        }
    ]


# =========================
# NORMALIZATION
# =========================

def normalize(r):
    return {
        "title": r["title"],
        "text": r["text"],
        "url": r["url"],
        "source": r["source"]
    }


# =========================
# INTELLIGENCE ENGINE
# =========================

def is_real_deal(text):
    DEAL_TERMS = ["acquire", "investment", "fund", "close", "financing", "stake"]
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

    if "fund" in t and ("close" in t or "launch" in t):
        return "FUND"

    if "acquire" in t or "investment" in t:
        return "INVESTMENT"

    if "debt" in t or "financing" in t:
        return "FINANCING"

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
# EXPOSURE ENGINE (KEY LOGIC)
# =========================

def infer_exposure(text, region, event_type):

    # ✅ cross-border proxy (correct approach, not currencies)
    cross_border = region != "US"

    # ✅ leverage detection → IR exposure
    leverage = "debt" in text.lower() or event_type == "FINANCING"

    return {
        "fx": cross_border,
        "ir": leverage
    }


# =========================
# PRIORITY MODEL
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
# MAIN PIPELINE
# =========================

@app.get("/")
def root():
    return {"status": "running"}


@app.get("/events")
def get_events():

    raw = []
    raw += fetch_rss()
    raw += fetch_registries()
    raw += fetch_social()

    processed = []

    for r in raw:
        n = normalize(r)
        text = n["text"]

        # ✅ STRICT FILTERING
        if not is_real_deal(text):
            continue

        if not is_illiquid_gp(text):
            continue

        event_type = classify(text)
        region = detect_region(text)

        exposure = infer_exposure(text, region, event_type)

        event = {
            **n,
            "region": region,
            "event_type": event_type,
            "fx": exposure["fx"],
            "ir": exposure["ir"]
        }

        event["priority"] = score(event)

        processed.append(event)

    return sorted(processed, key=lambda x: x["priority"], reverse=True)
