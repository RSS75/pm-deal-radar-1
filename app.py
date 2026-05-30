# ============================================================
# GP ACTIVITY INTELLIGENCE ENGINE (FULL SYSTEM VERSION)
# ============================================================

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import aiohttp
import feedparser
import re
import time
from datetime import datetime
from typing import List, Dict, Any, Optional

# ============================================================
# APP INIT
# ============================================================

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# CONFIG
# ============================================================

RSS_FEEDS = [
    "https://www.privateequityinternational.com/feed/",
    "https://www.inframationnews.com/feed/",
]

COMPANIES_HOUSE_API_KEY = "YOUR_KEY"

KEYWORDS = ["fund", "investment", "acquire", "close", "spv", "vehicle"]

GLOBAL_LOOP_INTERVAL = 2.0
MAX_STEP_RUNTIME = 1.5
MAX_CACHE_SIZE = 200

# ============================================================
# ENGINE STATE
# ============================================================

class SourceState:
    def __init__(self):
        self.fail_count = 0
        self.last_success = 0
        self.disabled_until = 0

class EngineState:
    def __init__(self):
        self.data: List[Dict] = []
        self.queue: List[Dict] = []
        self.step_index = 0
        self.running = False
        self.last_update = 0
        self.sources = {
            "rss": SourceState(),
            "registry": SourceState()
        }
        self.metrics = {
            "cycles": 0,
            "events_processed": 0
        }
        self.errors = {}

STATE = EngineState()

# ============================================================
# UTILITIES
# ============================================================

def now():
    return time.time()

def log(msg):
    print(f"[ENGINE] {msg}")

def is_valid(text: str) -> bool:
    try:
        return any(k in text.lower() for k in KEYWORDS)
    except:
        return False

def extract_entity(text: str) -> str:
    try:
        match = re.findall(r"\b(?:[A-Z][a-z]+(?:\s|$)){1,4}", text)
        return match[0].strip() if match else "Unknown"
    except:
        return "Unknown"

def classify(text: str) -> str:
    t = text.lower()
    if "fund" in t: return "FUND"
    if "investment" in t: return "INVESTMENT"
    if "spv" in t: return "STRUCTURE"
    return "OTHER"

# ============================================================
# SOURCE CONTROL (CIRCUIT BREAKER)
# ============================================================

def can_run(source_name):
    src = STATE.sources[source_name]
    if src.disabled_until > now():
        return False
    return True

def record_success(source_name):
    src = STATE.sources[source_name]
    src.fail_count = 0
    src.last_success = now()

def record_failure(source_name):
    src = STATE.sources[source_name]
    src.fail_count += 1

    if src.fail_count >= 3:
        src.disabled_until = now() + 30
        log(f"{source_name} disabled for 30 seconds")

# ============================================================
# SOURCE: RSS
# ============================================================

async def fetch_rss():
    results = []

    if not can_run("rss"):
        return results

    try:
        for url in RSS_FEEDS:

            feed = feedparser.parse(url)

            for e in feed.entries[:4]:
                text = (e.title or "") + " " + (e.get("summary", "") or "")

                if not is_valid(text):
                    continue

                results.append({
                    "title": e.title,
                    "text": text,
                    "url": e.link,
                    "source": "NEWS"
                })

        record_success("rss")

    except Exception as e:
        STATE.errors["rss"] = str(e)
        record_failure("rss")

    return results

# ============================================================
# SOURCE: REGISTRY
# ============================================================

async def fetch_registry(session):
    results = []

    if not can_run("registry"):
        return results

    try:
        async with session.get(
            "https://api.company-information.service.gov.uk/search/companies?q=fund",
            auth=aiohttp.BasicAuth(COMPANIES_HOUSE_API_KEY, ""),
            timeout=aiohttp.ClientTimeout(total=2)
        ) as resp:

            if resp.status != 200:
                raise Exception("Bad response")

            data = await resp.json()

            for item in data.get("items", [])[:3]:
                title = item.get("title", "")

                if not is_valid(title):
                    continue

                results.append({
                    "title": f"Registry: {title}",
                    "text": title,
                    "url": "https://find-and-update.company-information.service.gov.uk/company/" + item.get("company_number", ""),
                    "source": "REGISTRY"
                })

        record_success("registry")

    except Exception as e:
        STATE.errors["registry"] = str(e)
        record_failure("registry")

    return results

# ============================================================
# PROCESSING PIPELINE
# ============================================================

def deduplicate(events):
    seen = set()
    out = []

    for e in events:
        key = e["title"][:80]
        if key not in seen:
            seen.add(key)
            out.append(e)

    return out

def aggregate(events):
    grouped = {}

    for e in events:
        entity = extract_entity(e["text"])

        if entity not in grouped:
            grouped[entity] = {
                "entity": entity,
                "events": [],
                "activity_count": 0
            }

        grouped[entity]["events"].append({
            **e,
            "event_type": classify(e["text"])
        })

        grouped[entity]["activity_count"] += 1

    return list(grouped.values())

# ============================================================
# ENGINE EXECUTION STEPS
# ============================================================

async def execute_step(session):

    step = STATE.step_index % 2
    STATE.step_index += 1

    if step == 0:
        return await fetch_rss()
    else:
        return await fetch_registry(session)

# ============================================================
# MAIN ENGINE LOOP
# ============================================================

async def engine_loop():

    if STATE.running:
        return

    STATE.running = True

    session = aiohttp.ClientSession()

    log("Engine started")

    try:
        while True:

            cycle_start = now()
            step_data = []

            try:
                step_data = await execute_step(session)
            except Exception as e:
                STATE.errors["engine_step"] = str(e)

            # queue accumulation
            STATE.queue.extend(step_data)

            # bounded processing
            if len(STATE.queue) > 0:

                combined = STATE.data + STATE.queue
                combined = deduplicate(combined)

                STATE.data = aggregate(combined)[
                    :50
                ]  # memory limit

                STATE.queue = []
                STATE.last_update = now()

                STATE.metrics["events_processed"] += len(step_data)

            STATE.metrics["cycles"] += 1

            elapsed = now() - cycle_start

            # enforce time budget
            if elapsed < MAX_STEP_RUNTIME:
                await asyncio.sleep(MAX_STEP_RUNTIME - elapsed)

            await asyncio.sleep(GLOBAL_LOOP_INTERVAL)

    finally:
        await session.close()

# ============================================================
# START ENGINE
# ============================================================

@app.on_event("startup")
async def start_engine():
    asyncio.create_task(engine_loop())

# ============================================================
# API LAYER
# ============================================================

@app.get("/")
def root():
    return {
        "status": "running",
        "last_update": STATE.last_update,
        "events": len(STATE.data),
        "metrics": STATE.metrics,
        "errors": STATE.errors
    }

@app.get("/events")
def events():
    return STATE.data
