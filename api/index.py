"""FastAPI app — Vercel serverless compatible.
- SQLite stored in /tmp (writable on Vercel). Override with DB_PATH env var.
- CORS origins set via ALLOWED_ORIGINS env var (comma-separated) for production.
- No secrets, no external calls. All data is simulated/illustrative.
"""
import json
import sqlite3
import os
from dataclasses import asdict
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# scheduler.py lives in the same api/ directory
from scheduler import EV, DEFAULT_CFG, SEEDS, validate, simulate, compare

# ─── Storage ──────────────────────────────────────────────────────────────────
# /tmp is writable on Vercel serverless; falls back to DB_PATH env var for local dev
DB = os.environ.get("DB_PATH", "/tmp/ev_charging.db")

# ─── CORS ─────────────────────────────────────────────────────────────────────
# Set ALLOWED_ORIGINS="https://your-app.vercel.app" in Vercel project settings
_origins_env = os.environ.get(
    "ALLOWED_ORIGINS",
    "http://localhost:5173,http://localhost:3000,http://localhost:4173"
)
ALLOWED_ORIGINS = [o.strip() for o in _origins_env.split(",") if o.strip()]

# ─── App ──────────────────────────────────────────────────────────────────────
app = FastAPI(title="EV Charging Queue & Power Allocation Manager")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── DB helpers ───────────────────────────────────────────────────────────────
def db():
    c = sqlite3.connect(DB)
    c.execute("CREATE TABLE IF NOT EXISTS kv(k TEXT PRIMARY KEY, v TEXT)")
    return c


def load(k, default):
    r = db().execute("SELECT v FROM kv WHERE k=?", (k,)).fetchone()
    return json.loads(r[0]) if r else default


def save(k, v):
    c = db()
    c.execute("REPLACE INTO kv VALUES(?,?)", (k, json.dumps(v)))
    c.commit()


# ─── Models ───────────────────────────────────────────────────────────────────
class Req(BaseModel):
    id: str
    capacity_kwh: float
    soc: float
    arrival_h: float
    departure_h: float
    min_energy_kwh: float
    target_energy_kwh: float
    max_kw: float = 50
    trust: str = "claimed"


class RunBody(BaseModel):
    algorithm: str = "TAFCS"
    events: list[dict] = []
    sabotage: bool = False


# ─── Helpers ──────────────────────────────────────────────────────────────────
def current():
    reqs = load("requests", [asdict(e) for e in SEEDS["balanced"]])
    return [EV(**r) for r in reqs], {**DEFAULT_CFG, **load("settings", {})}


# ─── Routes ───────────────────────────────────────────────────────────────────
@app.get("/api/health")
def health():
    return {"status": "ok", "data": "simulated/illustrative demo data"}


@app.get("/api/settings")
def get_settings():
    return {**DEFAULT_CFG, **load("settings", {})}


@app.put("/api/settings")
def put_settings(s: dict):
    clean = {k: float(v) for k, v in s.items() if k in DEFAULT_CFG and float(v) >= 0}
    if clean.get("station_kw", 1) <= 0 or clean.get("chargers", 1) < 1:
        raise HTTPException(422, "invalid settings")
    save("settings", clean)
    return get_settings()


@app.get("/api/scenarios")
def scenarios():
    return {k: [asdict(e) for e in v] for k, v in SEEDS.items()}


@app.post("/api/scenarios/{name}/load")
def load_scenario(name: str):
    if name not in SEEDS:
        raise HTTPException(404, "unknown scenario")
    save("requests", [asdict(e) for e in SEEDS[name]])
    return {"loaded": name}


@app.get("/api/requests")
def list_requests():
    return load("requests", [asdict(e) for e in SEEDS["balanced"]])


@app.post("/api/requests")
def add_request(r: Req):
    errs, flags = validate(r.model_dump(), get_settings())
    if errs:
        raise HTTPException(422, {"rejected": True, "errors": errs})
    reqs = [x for x in list_requests() if x["id"] != r.id] + [r.model_dump()]
    save("requests", reqs)
    return {"accepted": True, "flags": flags}


@app.delete("/api/requests/{rid}")
def del_request(rid: str):
    save("requests", [x for x in list_requests() if x["id"] != rid])
    return {"deleted": rid}


@app.post("/api/validate")
def val(r: dict):
    e, f = validate(r, get_settings())
    return {"errors": e, "flags": f}


@app.post("/api/schedule")
def schedule(b: RunBody):
    evs, cfg = current()
    return simulate(evs, cfg, b.algorithm.upper(), b.events, b.sabotage)


@app.post("/api/compare")
def cmp(b: RunBody):
    evs, cfg = current()
    return compare(evs, cfg, b.events)
