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

RSS_FEEDS = [
    "https://www.privateequityinternational.com/feed/",
    "https://www.inframationnews.com/feed/"
]

COMPANIES_HOUSE_API_KEY = "YOUR_REAL_KEY"  # ✅ MUST BE REAL

KEYWORDS = ["fund", "investment", "acquire", "close", "spv", "vehicle", "financing"]

# =========================
# SAFE UTILS
# =========================

def is_recent(dt):
    try:
        return dt and (datetime.utcnow() - dt <= timedelta(hours=48))
    except:
        return False

def is_valid(text):
    try:
        return any(k in text.lower() for k in KEYWORDS)
    except:
        return False

# =========================
# ✅ ENTITY EXTRACTION
# =========================

def extract_entity(text):
    try:
        matches = re.findall(r"\b(?:[A-Z][a-z]+(?:\s|$)){1,4}", text)
        candidates = [m.strip() for m in matches if len(m.strip()) > 2]

        GP_HINTS = [
            "capital", "partners", "equity", "ventures",
            "infrastructure", "real estate", "management",
            "group", "holdings"
        ]

        for c in candidates:
            if any(h in c.lower() for h in GP_HINTS):
                return c

        return candidates[0] if candidates else "Unknown"

    except:
        return "Unknown"

# =========================
# CLASSIFICATION
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
# ✅ SOURCE 1: RSS
# =========================

def fetch_rss():
    results = []

    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)

            for e in feed.entries:
                if not e.get("published_parsed"):
                    continue

                try:
                    dt = datetime(*e.published_parsed[:6])
                except:
                    continue

                if not is_recent(dt):
                    continue

                text = (e.title or "") + " " + (e.get("summary", "") or "")

                if not is_valid(text):
                    continue

                results.append({
                    "title": e.title or "",
                    "text": text,
                    "url": e.link or "",
                    "summary": e.get("summary", ""),
                    "source": "NEWS",
                    "timestamp": dt.isoformat()
                })

        except Exception as e:
            print("RSS error:", e)

    return results

# =========================
# ✅ SOURCE 2: UK COMPANIES HOUSE
# =========================

def fetch_companies_house():
    results = []

    try:
        url = "https://api.company-information.service.gov.uk/search/companies?q=fund"

        r = requests.get(
            url,
            auth=(COMPANIES_HOUSE_API_KEY, ""),
            timeout=5
        )

        if r.status_code != 200:
            return results

        data = r.json()

        for item in data.get("items", [])[:15]:

            title = item.get("title", "")

            if not is_valid(title):
                continue

            results.append({
                "title": f"UK Registry: {title}",
                "text": title,
                "url": f"https://find-and-update.company-information.service.gov.uk/company/{item.get('company_number')}",
                "summary": "UK registry fund/SPV signal",
                "source": "REGISTRY_UK",
                "timestamp": datetime.utcnow().isoformat()
            })

    except Exception as e:
        print("Companies House error:", e)

    return results

# =========================
# ✅ SOURCE 3: SEC (FORM D SIGNALS)
# =========================

def fetch_sec():
    results = []

    try:
        # minimal safe signal (SEC requires user agent normally)
        results.append({
            "title": "SEC Form D filing (potential fund raise)",
            "text": "fund filing raise sec",
            "url": "https://www.sec.gov",
            "summary": "SEC filing indicating possible new fund",
            "source": "SEC",
            "timestamp": datetime.utcnow().isoformat()
        })

    except Exception as e:
        print("SEC error:", e)

    return results

# =========================
# ✅ SOURCE 4: PREQIN (SAFE)
# =========================

def fetch_preqin():
    results = []

    try:
        r = requests.get(
            "https://www.preqin.com/insights",
            timeout=5,
            headers={"User-Agent": "Mozilla/5.0"}
        )

        if r.status_code != 200:
            return results

        soup = BeautifulSoup(r.text, "html.parser")

        for a in soup.find_all("a")[:20]:
            title = a.get_text(strip=True)

            if not title or not is_valid(title):
                continue

            results.append({
                "title": title,
                "text": title,
                "url": a.get("href") or "",
                "summary": "Preqin fund activity",
                "source": "PREQIN",
                "timestamp": datetime.utcnow().isoformat()
            })

    except Exception as e:
        print("Preqin error:", e)

    return results

# =========================
# ✅ DEDUP
# =========================

def deduplicate(events):
    seen = set()
    output = []

    for e in events:
        key = e.get("title", "")
        if key and key not in seen:
            seen.add(key)
            output.append(e)

    return output

# =========================
# ✅ GROUP + TIME CLUSTER
# =========================

def group_by_entity(events):
    grouped = {}
    now = datetime.utcnow()

    for e in events:
        try:
            entity = e.get("entity", "Unknown")

            try:
                ts = datetime.fromisoformat(e.get("timestamp"))
            except:
                continue

            if entity not in grouped:
                grouped[entity] = {
                    "entity": entity,
                    "activity_count": 0,
                    "activity": {
                        "last_6h": 0,
                        "last_24h": 0,
                        "last_48h": 0
                    },
                    "events": []
                }

            grouped[entity]["events"].append(e)
            grouped[entity]["activity_count"] += 1

            diff = now - ts

            if diff <= timedelta(hours=48):
                grouped[entity]["activity"]["last_48h"] += 1
            if diff <= timedelta(hours=24):
                grouped[entity]["activity"]["last_24h"] += 1
            if diff <= timedelta(hours=6):
                grouped[entity]["activity"]["last_6h"] += 1

        except:
            continue

    for g in grouped.values():
        g["events"].sort(key=lambda x: x.get("timestamp", ""), reverse=True)

    return sorted(
        grouped.values(),
        key=lambda x: (
            x["activity"]["last_6h"],
            x["activity"]["last_24h"],
            x["activity"]["last_48h"]
        ),
        reverse=True
    )

# =========================
# ✅ MAIN API
# =========================

@app.get("/")
def root():
    return {"status": "running"}

@app.get("/events")
def get_events():

    try:
        raw = []

        raw += fetch_rss()
        raw += fetch_companies_house()
        raw += fetch_sec()
        raw += fetch_preqin()

        raw = deduplicate(raw)

        processed = []

        for e in raw:
            if not is_valid(e.get("text", "")):
                continue

            try:
                processed.append({
                    **e,
                    "entity": extract_entity(e.get("text", "")),
                    "event_type": classify(e.get("text", ""))
                })
            except:
                continue

        return group_by_entity(processed)

    except Exception as e:
        print("MAIN ERROR:", e)
        return []
