# EV Charging Queue & Power Allocation Manager

> Smart EV charging queue manager using TAFCS, FCFS, and EDF scheduling algorithms. All data is simulated/illustrative — no real hardware or telemetry connected.

---

## 🚀 Deploy to Vercel (One Click)

[![Deploy with Vercel](https://vercel.com/button)](https://vercel.com/new/clone?repository-url=https://github.com/Krishninghot/EV-Charging)

### Manual Vercel Deployment

1. Push to GitHub (already done ✅)
2. Go to [vercel.com](https://vercel.com) → **New Project** → Import `EV-Charging`
3. Leave all settings as default (vercel.json handles everything)
4. Add environment variables in Vercel Project Settings:

| Variable | Value |
|----------|-------|
| `ALLOWED_ORIGINS` | `https://your-app.vercel.app` |
| `VITE_API_BASE_URL` | *(leave empty — uses same domain)* |

5. Click **Deploy** 🎉

---

## 💻 Local Development (Windows PowerShell)

```powershell
# Backend (Python 3.10+)
cd backend
python -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn main:app --port 8000

# Frontend (Node 18+) — new terminal
cd frontend
npm install
npm run dev     # http://localhost:5173 (proxies /api → :8000)

# Tests
cd backend
python -m unittest discover -s tests
```

### Environment Setup (local)
```powershell
# Copy the example file and edit as needed
Copy-Item .env.example .env
```

---

## 📁 Project Structure

```
EV-Charging/
├── api/                    # Vercel serverless Python functions
│   ├── index.py            # FastAPI app (Vercel entry point)
│   └── scheduler.py        # TAFCS scheduling engine
├── backend/                # Local development backend (same logic)
│   ├── main.py
│   ├── scheduler.py
│   └── tests/
├── frontend/               # React + Vite + TypeScript + Tailwind
│   ├── src/
│   │   ├── App.tsx
│   │   └── main.tsx
│   └── index.html
├── vercel.json             # Vercel deployment configuration
├── requirements.txt        # Python deps (used by Vercel)
├── .env.example            # Environment variable template
└── README.md
```

---

## 🌐 API Reference

All endpoints are under `/api`:

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/health` | Health check |
| `GET/PUT` | `/api/settings` | Station configuration |
| `GET` | `/api/scenarios` | Available seed scenarios |
| `POST` | `/api/scenarios/{name}/load` | Load a scenario (`balanced`, `overloaded`, `infeasible`) |
| `GET/POST` | `/api/requests` | List / add EV charging requests |
| `DELETE` | `/api/requests/{id}` | Remove an EV request |
| `POST` | `/api/validate` | Validate an EV request without adding |
| `POST` | `/api/schedule` | Run scheduling simulation `{algorithm, events, sabotage}` |
| `POST` | `/api/compare` | Compare all algorithms on same input |

**Event types:** `power_reduction{t,factor}` · `charger_failure{t,count}` · `departure{t,id}` · `arrival{t,ev}`

---

## 🧮 Scheduling Model

- **Units:** kWh, kW, hours; time step = 0.25 h
- **Score (0–100):** `100 × (w_u×urgency×conf + w_t×conf + w_w×wait) / Σw`
  - `urgency = min(min_kWh / (max_kW × time_left), 1)`
  - `conf`: verified=1.0, estimated=0.6, claimed=0.4 *(illustrative)*
  - `wait = min(wait_time / max_wait, 1)`
- **TAFCS:** Pass 1 = minimum needs by rank; Pass 2 = remaining capacity toward targets
- **FCFS/EDF:** Greedy fill to target sorted by arrival/deadline
- **Safety checker:** Validates station limit, connector count, per-vehicle ratings; unsafe plans are rejected and deterministically clamped

---

## ⚠️ Limitations

- Greedy per-step heuristic (not globally optimal)
- SQLite in `/tmp` on Vercel — data resets on cold start (demo-only)
- No authentication, no real telemetry/hardware
- Scheduling weights are illustrative and unvalidated
