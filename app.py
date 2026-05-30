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

COMPANIES_HOUSE_API_KEY = "YOUR_KEY"
KEYWORDS = ["fund", "investment", "acquire", "close", "spv", "vehicle", "financing"]

RSS_FEEDS = [
    "https://www.privateequityinternational.com/feed/",
    "https://www.inframationnews.com/feed/"
]

# Global registry proxies (STABLE RSS)
LUX_RSS = "https://www.cssf.lu/en/rss/"
IRELAND_RSS = "https://www.centralbank.ie/news/rss"

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
    if not dt:
        return False
    return datetime.utcnow() - dt <= timedelta(hours=48)

def is_valid(text):
    return text and any(k in text.lower() for k in KEYWORDS)

# =========================
# ENTITY EXTRACTION + NORMALISATION
# =========================

def normalize_entity(name):
    name = name.strip()

    # collapse long names → core identity
    replacements = [
        ("Capital Partners", "Capital"),
        ("Infrastructure Partners", "Infrastructure"),
        ("Private Equity", ""),
        ("Holdings", "")
    ]

    for k, v in replacements:
        name = name.replace(k, v)

    return name.strip()

def extract_entity(text):
    try:
        matches = re.findall(r"\b(?:[A-Z][a-z]+(?:\s|$)){1,4}", text)
        candidates = [m.strip() for m in matches if len(m.strip()) > 2]

        GP_HINTS = [
            "capital", "partners", "equity", "ventures",
            "infrastructure", "real estate", "group"
        ]

        for c in candidates:
            if any(h in c.lower() for h in GP_HINTS):
                return normalize_entity(c)

        return normalize_entity(candidates[0]) if candidates else "Unknown"

    except:
        return "Unknown"

# =========================
# CLASSIFY
# =========================

def classify(text):
    try:
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

    except:
        return "OTHER"

# =========================
# SOURCE: RSS NEWS
# =========================

def fetch_rss():
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

    return out

# =========================
# SOURCE: COMPANIES HOUSE
# =========================

def fetch_uk_registry():
    out = []

    try:
        r = requests.get(
            "https://api.company-information.service.gov.uk/search/companies?q=fund",
            auth=(COMPANIES_HOUSE_API_KEY, ""),
            timeout=5
        )

        items = r.json().get("items", [])

        for i in items[:10]:
            title = i.get("title", "")

            if not is_valid(title):
                continue

            out.append({
                "title": f"UK Registry: {title}",
                "text": title,
                "url": "https://find-and-update.company-information.service.gov.uk/company/" + i.get("company_number", ""),
                "summary": "UK fund/SPV registration",
                "source": "REGISTRY_UK",
                "timestamp": safe_time(datetime.utcnow())
            })

    except:
        pass

    return out

# =========================
# SOURCE: LUX + IRELAND
# =========================

def fetch_registry_rss(url, label):
    out = []

    try:
        feed = feedparser.parse(url)

        for e in feed.entries[:10]:
            try:
                dt = datetime(*e.published_parsed[:6])
            except:
                continue

            ts = safe_time(dt)

            if not is_recent(ts):
                continue

            text = e.title or ""

            if not is_valid(text):
                continue

            out.append({
                "title": e.title,
                "text": text,
                "url": e.link,
                "summary": f"{label} registry signal",
                "source": label,
                "timestamp": ts
            })

    except:
        pass

    return out

# =========================
# SOURCE: SEC EDGAR (REAL SAFE SCRAPE)
# =========================

def fetch_sec():
    out = []

    try:
        r = requests.get(
            "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=5
        )

        soup = BeautifulSoup(r.text, "html.parser")

        rows = soup.find_all("tr")

        for r in rows[:20]:
            text = r.get_text(" ", strip=True)

            if "D" not in text:
                continue

            if not is_valid(text):
                continue

            out.append({
                "title": text[:120],
                "text": text,
                "url": "https://www.sec.gov",
                "summary": "SEC Form D filing",
                "source": "SEC",
                "timestamp": safe_time(datetime.utcnow())
            })

    except:
        pass

    return out

# =========================
# PREQIN
# =========================

def fetch_preqin():
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

    return out

# =========================
# PIPELINE
# =========================

def dedupe(events):
    seen = set()
    out = []
    for e in events:
        k = e.get("title", "")
        if k and k not in seen:
            seen.add(k)
            out.append(e)
    return out

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

    return sorted(
        g.values(),
        key=lambda x: (x["activity"]["last_6h"], x["activity"]["last_24h"]),
        reverse=True
    )

# =========================
# MAIN
# =========================

@app.get("/events")
def get_events():
    try:
        raw = []
        raw += fetch_rss()
        raw += fetch_uk_registry()
        raw += fetch_registry_rss(LUX_RSS, "REGISTRY_LUX")
        raw += fetch_registry_rss(IRELAND_RSS, "REGISTRY_IE")
        raw += fetch_sec()
        raw += fetch_preqin()

        raw = dedupe(raw)

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

    except:
        return []
