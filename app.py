from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import feedparser
from datetime import datetime

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

RSS_FEEDS = [
    "https://www.privateequityinternational.com/feed/",
    "https://www.inframationnews.com/feed/",
    "https://www.ft.com/rss/home"
]

KEYWORDS = ["fund", "investment", "acquire", "deal", "raise"]

def is_relevant(text):
    return any(k in text.lower() for k in KEYWORDS)

def detect_region(text):
    t = text.lower()
    if "europe" in t: return "Europe"
    if "asia" in t: return "Asia"
    if "uk" in t: return "UK"
    if "us" in t: return "US"
    return "Global"

def detect_asset(text):
    t = text.lower()
    if "infrastructure" in t: return "Infrastructure"
    if "real estate" in t: return "Real Estate"
    if "debt" in t: return "Private Debt"
    if "venture" in t or "vc" in t: return "VC"
    return "Private Equity"

def detect_fx(text):
    return any(k in text.lower() for k in ["europe", "asia", "cross-border", "usd", "eur"])

def detect_ir(text):
    return any(k in text.lower() for k in ["debt", "financing", "yield", "leverage"])

def score_event(text, fx, ir):
    score = 0
    if fx: score += 2
    if ir: score += 2
    if "acquire" in text.lower() or "deal" in text.lower():
        score += 1
    return score

@app.get("/")
def root():
    return {"status": "running"}

@app.get("/events")
def get_events():

    events = []

    for url in RSS_FEEDS:
        feed = feedparser.parse(url)

        for entry in feed.entries[:15]:
            text = f"{entry.title} {entry.get('summary','')}"

            if not is_relevant(text):
                continue

            fx = detect_fx(text)
            ir = detect_ir(text)

            event = {
                "title": entry.title,
                "article_url": entry.link,
                "region": detect_region(text),
                "asset_class": detect_asset(text),
                "fx": fx,
                "ir": ir,
                "priority": score_event(text, fx, ir),
                "timestamp": entry.get("published", "")
            }

            events.append(event)

    return events
