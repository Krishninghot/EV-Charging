"""TAFCS scheduler. Units: kWh energy, kW power, hours time. Deterministic, stdlib only."""
from dataclasses import dataclass, field, asdict
from typing import Optional
DT = 0.25  # h per step
TRUST_CONF = {"verified": 1.0, "estimated": 0.6, "claimed": 0.4}  # ILLUSTRATIVE, unvalidated weights
DEFAULT_CFG = {"station_kw": 100.0, "chargers": 4, "charger_kw": 50.0, "horizon_h": 12.0,
               "w_urgency": 0.5, "w_trust": 0.2, "w_wait": 0.3, "max_wait_h": 3.0}

@dataclass
class EV:
    id: str; capacity_kwh: float; soc: float; arrival_h: float; departure_h: float
    min_energy_kwh: float; target_energy_kwh: float; max_kw: float = 50.0; trust: str = "claimed"
    def need_to_full(self): return self.capacity_kwh * (1 - self.soc)

def validate(d: dict, cfg=None):
    """Returns (errors, flags). errors => rejected; flags => accepted with warning."""
    cfg = {**DEFAULT_CFG, **(cfg or {})}; e, f = [], []
    try:
        cap, soc, a, dep = float(d["capacity_kwh"]), float(d["soc"]), float(d["arrival_h"]), float(d["departure_h"])
        mn, tg, mk = float(d["min_energy_kwh"]), float(d["target_energy_kwh"]), float(d.get("max_kw", 50))
    except (KeyError, TypeError, ValueError):
        return ["missing or non-numeric field"], []
    if not str(d.get("id", "")).strip(): e.append("vehicle id required")
    if d.get("trust", "claimed") not in TRUST_CONF: e.append("trust must be verified|claimed|estimated")
    if not 5 <= cap <= 300: e.append("battery capacity must be 5-300 kWh")
    if not 0 <= soc <= 1: e.append("SoC must be within 0-1")
    if mk <= 0: e.append("vehicle max kW must be > 0")
    if a < 0 or dep <= a: e.append("departure must be after arrival (impossible deadline)")
    if mn < 0 or tg < mn: e.append("target must be >= minimum energy >= 0")
    if e: return e, f
    room = cap * (1 - soc)
    if tg > room + 1e-9: e.append(f"target {tg} kWh exceeds remaining battery room {room:.1f} kWh (inconsistent SoC/capacity)")
    if e: return e, f
    if mn > min(mk, cfg["charger_kw"]) * (dep - a) + 1e-9: f.append("infeasible: minimum energy cannot be delivered even at full power in the window")
    if d.get("trust") == "claimed": f.append("user-claimed values: unverified")
    return e, f

def score(ev: EV, t, cfg, first_wait):
    """All components normalized to 0-1; score on 0-100. Unverified urgency is discounted by trust confidence."""
    conf = TRUST_CONF[ev.trust]
    window = max(ev.departure_h - max(t, ev.arrival_h), DT)
    urg = min(1.0, ev.min_energy_kwh / (min(ev.max_kw, cfg["charger_kw"]) * window))
    wait = min(1.0, first_wait / cfg["max_wait_h"])
    s = cfg["w_urgency"] * urg * conf + cfg["w_trust"] * conf + cfg["w_wait"] * wait
    return 100 * s / (cfg["w_urgency"] + cfg["w_trust"] + cfg["w_wait"]), dict(urgency=urg, trust=conf, wait=wait)

def safety_check(alloc, evs, cfg, station_kw, n_conn, t):
    """Independent checker: returns list of violations."""
    v = []
    if sum(alloc.values()) > station_kw + 1e-6: v.append("station power exceeded")
    if sum(1 for p in alloc.values() if p > 1e-9) > n_conn: v.append("connector count exceeded")
    for i, p in alloc.items():
        ev = evs[i]
        if p < -1e-9 or p > min(ev.max_kw, cfg["charger_kw"]) + 1e-6: v.append(f"{i}: rating exceeded")
        if p > 1e-9 and not (ev.arrival_h - 1e-9 <= t < ev.departure_h): v.append(f"{i}: outside window")
        if p * DT > ev.need_to_full() - 0 + 1e-6 and p > 0 and ev.need_to_full() < 1e-9: v.append(f"{i}: battery full")
    return v

def _clamp(alloc, evs, cfg, station_kw, n_conn):
    """Recalculation path: deterministic repair of an unsafe plan."""
    out, left = {}, station_kw
    for i, p in sorted(alloc.items(), key=lambda kv: -kv[1])[:n_conn]:
        q = max(0.0, min(p, evs[i].max_kw, cfg["charger_kw"], left)); out[i] = q; left -= q
    return out

def simulate(evs_in, cfg=None, algo="TAFCS", events=None, sabotage=False):
    cfg = {**DEFAULT_CFG, **(cfg or {})}; events = sorted(events or [], key=lambda x: x["t"])
    evs = {e.id: e for e in evs_in}; delivered = {i: 0.0 for i in evs}; first = {}; done_t = {}
    log, timeline, rejections = [], [], []
    station, working, charger_kw = cfg["station_kw"], cfg["chargers"], cfg["charger_kw"]
    cap_int = 0.0; used_int = 0.0; ei = 0; t = 0.0; snap = None
    while t < cfg["horizon_h"] - 1e-9:
        while ei < len(events) and events[ei]["t"] <= t + 1e-9:
            ev_ = events[ei]; ei += 1
            if ev_["type"] == "power_reduction": station *= ev_.get("factor", 0.5)
            elif ev_["type"] == "charger_failure": working = max(0, working - ev_.get("count", 1))
            elif ev_["type"] == "departure" and ev_["id"] in evs: evs[ev_["id"]].departure_h = min(evs[ev_["id"]].departure_h, t)
            elif ev_["type"] == "arrival": e = EV(**ev_["ev"]); evs[e.id] = e; delivered[e.id] = 0.0
            log.append(dict(t=t, event=ev_["type"], detail=f"station={station:.0f} kW, chargers={working}", reschedule=True))
        active = [e for e in evs.values() if e.arrival_h <= t + 1e-9 < e.departure_h and e.need_to_full() - delivered[e.id] > 1e-9
                  and delivered[e.id] < e.target_energy_kwh - 1e-9]
        sc = {}
        for e in active:
            s, comp = score(e, t, cfg, t - e.arrival_h if e.id not in first else 0.0); sc[e.id] = (s, comp)
        if algo == "FCFS": order = sorted(active, key=lambda e: (e.arrival_h, e.id))
        elif algo == "EDF": order = sorted(active, key=lambda e: (e.departure_h, e.id))
        else: order = sorted(active, key=lambda e: (-sc[e.id][0], e.id))
        alloc = {e.id: 0.0 for e in order}; left = station
        cap_ = lambda e: min(e.max_kw, charger_kw)
        for rank, e in enumerate(order):
            if rank >= working: break
            if algo == "TAFCS":  # pass 1: minimum need, jointly feasible by rank
                need_min = max(0.0, e.min_energy_kwh - delivered[e.id])
                p = min(cap_(e), left, need_min / DT)
            else:  # baselines: greedy straight to target
                p = min(cap_(e), left, (e.target_energy_kwh - delivered[e.id]) / DT)
            alloc[e.id] = max(0.0, p); left -= alloc[e.id]
        if algo == "TAFCS":  # pass 2: leftover toward preferred targets
            for rank, e in enumerate(order):
                if rank >= working: break
                p = min(cap_(e) - alloc[e.id], left, (e.target_energy_kwh - delivered[e.id]) / DT - alloc[e.id])
                if p > 0: alloc[e.id] += p; left -= p
        if sabotage and t == 0 and alloc:  # demo of unsafe plan rejection
            k = next(iter(alloc)); alloc[k] += station
        viol = safety_check(alloc, evs, cfg, station, working, t)
        if viol:
            rejections.append(dict(t=t, violations=viol)); alloc = _clamp(alloc, evs, cfg, station, working)
            assert not safety_check(alloc, evs, cfg, station, working, t)
        for i, p in alloc.items():
            if p > 1e-9:
                first.setdefault(i, t); delivered[i] += p * DT
                if delivered[i] >= evs[i].target_energy_kwh - 1e-9: done_t.setdefault(i, t + DT)
        cap_int += station * DT; used_int += sum(alloc.values()) * DT
        timeline.append(dict(t=round(t, 2), station_kw=station, used_kw=round(sum(alloc.values()), 2),
                             alloc={i: round(p, 2) for i, p in alloc.items()},
                             scores={i: round(sc[i][0], 1) for i in sc}))
        if snap is None: snap = (dict(alloc), {i: sc[i] for i in sc}, [e.id for e in order])
        t = round(t + DT, 6)
    return _results(evs, delivered, first, done_t, cap_int, used_int, timeline, log, rejections, snap, algo, cfg)

def _results(evs, delivered, first, done_t, cap_int, used_int, timeline, log, rejections, snap, algo, cfg):
    rows, waits = [], []
    for i, e in evs.items():
        d = delivered[i]; mn_ok = d >= e.min_energy_kwh - 1e-6; tg_ok = d >= e.target_energy_kwh - 1e-6
        w = first.get(i, e.departure_h) - e.arrival_h; waits.append(max(0, w))
        feasible = e.min_energy_kwh <= min(e.max_kw, cfg["charger_kw"]) * (e.departure_h - e.arrival_h) + 1e-9
        status = "completed" if tg_ok else "minimum met (partial)" if mn_ok else "infeasible" if not feasible else "deadline missed"
        why = (f"Delivered {d:.1f}/{e.target_energy_kwh:.1f} kWh target (min {e.min_energy_kwh:.1f}). Trust={e.trust}; waited {w:.2f} h. " +
               ("Minimum need physically impossible in window at rated power." if not feasible else
                "Minimum not met: station power/connectors were contended." if not mn_ok else
                "Minimum met; remaining power went to higher-ranked EVs before the target." if not tg_ok else "Target met."))
        rows.append(dict(id=i, trust=e.trust, delivered_kwh=round(d, 2), min_kwh=e.min_energy_kwh, target_kwh=e.target_energy_kwh,
                         wait_h=round(w, 2), min_met=mn_ok, target_met=tg_ok, status=status, completion_h=done_t.get(i),
                         initial_kw=round(snap[0].get(i, 0), 2) if snap else 0, initial_score=round(snap[1][i][0], 1) if snap and i in snap[1] else None,
                         initial_rank=snap[2].index(i) + 1 if snap and i in snap[2] else None, explanation=why))
    n = max(1, len(evs))
    metrics = dict(avg_wait_h=round(sum(waits) / n, 3), deadline_misses=sum(1 for r in rows if not r["min_met"]),
                   min_fulfillment_pct=round(100 * sum(r["min_met"] for r in rows) / n, 1),
                   target_fulfillment_pct=round(100 * sum(r["target_met"] for r in rows) / n, 1),
                   utilization_pct=round(100 * used_int / cap_int, 1) if cap_int else 0.0, energy_kwh=round(used_int, 2))
    return dict(algorithm=algo, metrics=metrics, evs=rows, timeline=timeline, events=log, safety_rejections=rejections)

def compare(evs, cfg=None, events=None):
    return {a: simulate([EV(**asdict(e)) for e in evs], cfg, a, events) for a in ("TAFCS", "FCFS", "EDF")}

SEEDS = {
 "balanced": [EV("EV-101", 60, .30, 0, 6, 15, 30, 50, "verified"), EV("EV-102", 40, .50, 0.5, 4, 8, 16, 22, "verified"),
              EV("EV-103", 75, .20, 1, 8, 20, 45, 50, "estimated"), EV("EV-104", 50, .60, 1, 3, 10, 18, 50, "claimed")],
 "overloaded": [EV(f"EV-2{k}", 60, .2, 0, 3, 20, 35, 50, "verified" if k % 2 else "claimed") for k in range(8)],
 "infeasible": [EV("EV-301", 60, .1, 0, 0.5, 30, 40, 50, "claimed"), EV("EV-302", 50, .4, 0, 5, 10, 20, 50, "verified")],
}
