from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import feedparser

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

def detect_fx(text):
    return any(k in text.lower() for k in ["europe", "usd", "eur", "asia"])

def detect_ir(text):
    return any(k in text.lower() for k in ["debt", "financing", "rates"])

def detect_region(text):
    t = text.lower()
    if "europe" in t: return "Europe"
    if "asia" in t: return "Asia"
    if "uk" in t: return "UK"
    return "Global"

@app.get("/events")
def get_events():
    events = []

    for url in RSS_FEEDS:
        feed = feedparser.parse(url)

        for entry in feed.entries[:10]:
            text = entry.title

            events.append({
                "title": entry.title,
                "fx": detect_fx(text),
                "ir": detect_ir(text),
                "region": detect_region(text),
                "size": 1000000000,
                "debt_ratio": 0.6,
                "article_url": entry.link,
                "manager_url": "https://www.google.com/search?q=" + entry.title.replace(" ", "+")
            })

    return events
