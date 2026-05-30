# ============================================================
# GP ACTIVITY ENGINE - FULL PIPELINED SYSTEM (500+ LINES)
# ============================================================

# =========================
# IMPORTS
# =========================

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import asyncio
import aiohttp
import feedparser

import re
import time

from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional


# =========================
# APP INIT
# =========================

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# CONFIGURATION
# ============================================================

RSS_FEEDS = [
    {"name": "pei", "url": "https://www.privateequityinternational.com/feed/"},
    {"name": "infra", "url": "https://www.inframationnews.com/feed/"},
]

COMPANIES_HOUSE_API_KEY = "YOUR_KEY_HERE"

KEYWORDS = [
    "fund",
    "investment",
    "acquire",
    "close",
    "spv",
    "vehicle"
]

# ENGINE TIMING (SLOWED DOWN DELIBERATELY)
STEP_DELAY = 1.5
ENGINE_LOOP_DELAY = 2.5

RSS_REFRESH_INTERVAL = 120
REGISTRY_REFRESH_INTERVAL = 60

MAX_EVENTS_MEMORY = 200


# ============================================================
# TIME UTILITIES
# ============================================================

def now_dt() -> datetime:
    return datetime.utcnow()

def now_ts() -> float:
    return time.time()

def within_48h(ts: datetime) -> bool:
    return (now_dt() - ts) <= timedelta(hours=48)


# ============================================================
# VALIDATION / EXTRACTION
# ============================================================

def is_valid(text: str) -> bool:
    try:
        return any(k in text.lower() for k in KEYWORDS)
    except:
        return False


def extract_entity(text: str) -> str:
    try:
        matches = re.findall(r"\b(?:[A-Z][a-z]+(?:\s|$)){1,4}", text)
        return matches[0].strip() if matches else "Unknown"
    except:
        return "Unknown"


def classify(text: str) -> str:
    t = text.lower()

    if "fund" in t:
        return "FUND"
    if "investment" in t:
        return "INVESTMENT"
    if "spv" in t:
        return "STRUCTURE"

    return "OTHER"


# ============================================================
# DATA MODELS
# ============================================================

class Event:

    def __init__(
        self,
        title: str,
        text: str,
        url: str,
        source: str
    ):
        self.title = title
        self.text = text
        self.url = url
        self.source = source
        self.timestamp = now_dt()

    def to_dict(self) -> Dict:
        return {
            "title": self.title,
            "text": self.text,
            "url": self.url,
            "source": self.source,
            "timestamp": self.timestamp.isoformat()
        }


class Task:

    def __init__(
        self,
        name: str,
        payload: Optional[Dict] = None
    ):
        self.name = name
        self.payload = payload
        self.created = now_ts()


class SourceState:

    def __init__(self):
        self.failures = 0
        self.disabled_until = 0


# ============================================================
# ENGINE STATE
# ============================================================

class EngineState:

    def __init__(self):

        self.events: List[Event] = []
        self.queue: List[Task] = []

        self.last_rss_refresh = 0
        self.last_registry_refresh = 0

        self.metrics = {
            "cycles": 0,
            "tasks_processed": 0,
            "events_total": 0
        }

        self.errors: Dict[str, Any] = {}

        self.sources = {
            "rss": SourceState(),
            "registry": SourceState()
        }


STATE = EngineState()


# ============================================================
# SOURCE CONTROL (CIRCUIT BREAKER)
# ============================================================

def can_run_source(name: str) -> bool:
    state = STATE.sources[name]
    return now_ts() > state.disabled_until


def record_success(name: str):
    STATE.sources[name].failures = 0


def record_failure(name: str):
    s = STATE.sources[name]
    s.failures += 1

    if s.failures >= 3:
        s.disabled_until = now_ts() + 30
        s.failures = 0


# ============================================================
# SCHEDULER
# ============================================================

def schedule_rss_tasks():
    for feed in RSS_FEEDS:
        STATE.queue.append(Task("rss", feed))


def schedule_registry_task():
    STATE.queue.append(Task("registry"))


def scheduler_cycle():

    t = now_ts()

    if t - STATE.last_rss_refresh > RSS_REFRESH_INTERVAL:
        schedule_rss_tasks()
        STATE.last_rss_refresh = t

    if t - STATE.last_registry_refresh > REGISTRY_REFRESH_INTERVAL:
        schedule_registry_task()
        STATE.last_registry_refresh = t


# ============================================================
# RSS HANDLER
# ============================================================

async def run_rss_task(task: Task):

    if not can_run_source("rss"):
        return

    try:
        feed = feedparser.parse(task.payload["url"])

        for entry in feed.entries[:5]:

            text = (entry.title or "") + " " + (entry.get("summary") or "")

            if not is_valid(text):
                continue

            event = Event(
                entry.title,
                text,
                entry.link,
                "NEWS"
            )

            STATE.events.append(event)

        record_success("rss")

    except Exception as e:
        STATE.errors["rss"] = str(e)
        record_failure("rss")


# ============================================================
# REGISTRY HANDLER
# ============================================================

async def run_registry_task():

    if not can_run_source("registry"):
        return

    try:

        async with aiohttp.ClientSession() as session:

            async with session.get(
                "https://api.company-information.service.gov.uk/search/companies?q=fund",
                auth=aiohttp.BasicAuth(COMPANIES_HOUSE_API_KEY, ""),
                timeout=aiohttp.ClientTimeout(total=3)
            ) as resp:

                if resp.status != 200:
                    return

                data = await resp.json()

                for item in data.get("items", [])[:3]:

                    title = item.get("title")

                    if not is_valid(title):
                        continue

                    event = Event(
                        title,
                        title,
                        "https://find-and-update.company-information.service.gov.uk/company/" + item.get("company_number"),
                        "REGISTRY"
                    )

                    STATE.events.append(event)

        record_success("registry")

    except Exception as e:
        STATE.errors["registry"] = str(e)
        record_failure("registry")


# ============================================================
# TASK EXECUTOR
# ============================================================

async def execute_next_task():

    if not STATE.queue:
        return

    task = STATE.queue.pop(0)

    if task.name == "rss":
        await run_rss_task(task)

    elif task.name == "registry":
        await run_registry_task()

    STATE.metrics["tasks_processed"] += 1


# ============================================================
# DATA PROCESSING PIPELINE
# ============================================================

def prune_old_events():

    STATE.events = [
        e for e in STATE.events if within_48h(e.timestamp)
    ]


def deduplicate_events():

    seen = set()
    unique = []

    for e in STATE.events:
        key = e.title[:80]

        if key not in seen:
            seen.add(key)
            unique.append(e)

    STATE.events = unique


def enforce_memory_limit():
    STATE.events = STATE.events[:MAX_EVENTS_MEMORY]


# ============================================================
# AGGREGATION
# ============================================================

def aggregate_events():

    grouped = {}

    for e in STATE.events:

        entity = extract_entity(e.text)

        if entity not in grouped:
            grouped[entity] = {
                "entity": entity,
                "events": [],
                "activity_count": 0
            }

        grouped[entity]["events"].append({
            "title": e.title,
            "url": e.url,
            "source": e.source,
            "event_type": classify(e.text)
        })

        grouped[entity]["activity_count"] += 1

    return list(grouped.values())


# ============================================================
# ENGINE LOOP
# ============================================================

async def engine_loop():

    while True:

        try:

            # 1. schedule
            scheduler_cycle()

            # 2. execute ONE task only
            await execute_next_task()

            # 3. pipeline cleanup
            prune_old_events()
            deduplicate_events()
            enforce_memory_limit()

            # 4. metrics update
            STATE.metrics["cycles"] += 1
            STATE.metrics["events_total"] = len(STATE.events)

        except Exception as e:
            STATE.errors["engine"] = str(e)

        await asyncio.sleep(STEP_DELAY)


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
        "metrics": STATE.metrics,
        "queue_size": len(STATE.queue),
        "errors": STATE.errors
    }


@app.get("/events")
def events():
    return aggregate_events()
