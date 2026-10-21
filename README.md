# EV Charging Queue & Power Allocation Manager — SIH MVP (illustrative demo data)

## Run (Windows PowerShell)
```powershell
# Backend (Python 3.10+)
cd backend
python -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn main:app --port 8000
# Frontend (Node 18+), new terminal
cd frontend
npm install
npm run dev     # http://localhost:5173 (proxies /api to :8000)
# Tests
cd backend; python -m unittest discover -s tests
```
## API (all under /api)
GET health · GET/PUT settings · GET scenarios · POST scenarios/{name}/load · GET/POST requests · DELETE requests/{id} · POST validate · POST schedule {algorithm, events, sabotage} · POST compare {events}
Event types: power_reduction{t,factor}, charger_failure{t,count}, departure{t,id}, arrival{t,ev}.

## Model
Units: kWh, kW, hours; step 0.25 h. Energy = power x dt. Room = capacity x (1 - SoC).
Score (0-100) = 100 x (w_u*urgency*conf + w_t*conf + w_w*wait) / sum(w). urgency = min_kWh / (min(vehicle kW, charger kW) x time left), clipped to 1; conf: verified 1.0, estimated 0.6, claimed 0.4 (illustrative, unvalidated); wait = min(wait/max_wait, 1).
Scheduling per step: rank by score; Pass 1 gives each ranked EV (up to working chargers) power for its remaining minimum; Pass 2 spends leftover toward targets. An independent checker verifies station limit, connectors, ratings, windows; unsafe plans are rejected and deterministically clamped.
FCFS/EDF rank by arrival/departure and fill straight to target. Metrics are identical across algorithms. Utilization = energy delivered / (station kW integrated over the 12 h horizon), so it is low for light scenarios.

## Verification status
Verified: 8 backend unit tests on the scheduler (validation, scoring, min-need, power limits, infeasibility, power-cut and charger-failure rescheduling, unsafe-plan rejection, benchmark determinism).
NOT verified in the build environment (no network): FastAPI app, `npm install`, `tsc`, and the React UI were not executed. Expect to fix small issues on first run.
## Limitations / planned
Greedy per-step heuristic, not globally optimal; no preemption cost; weights unvalidated; no auth; no real telemetry/hardware; offline use not tested; settings editor UI and per-EV timeline charts are planned (settings available via API).
