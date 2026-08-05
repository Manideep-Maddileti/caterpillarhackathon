# Smart Rental Intelligence Platform

A dealer-personalized, AI-assisted equipment rental tracking platform for construction &amp; infrastructure fleets. Built for a Caterpillar-style hackathon brief.

Real-time equipment status and GPS tracking, QR-based check-in/check-out, automatic overdue alerts, rule-based demand forecasting and anomaly detection, explainable predictive maintenance scoring, and a conversational multi-agent AI assistant (LangGraph + Groq) — all scoped to a single dealer managing a personalized 10-vehicle fleet across India.

## Documentation

| Doc | Covers |
|---|---|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | System design, data flow, database schema, backend design principles |
| [docs/API_REFERENCE.md](docs/API_REFERENCE.md) | Every REST endpoint, request/response shapes |
| [docs/AI_AGENTS.md](docs/AI_AGENTS.md) | The orchestrator + 5 specialist agents, their tools, example routing |
| [docs/TELEMETRY_SIMULATOR.md](docs/TELEMETRY_SIMULATOR.md) | The realistic live-data simulator (`feature/realtime-telemetry-simulator` branch) — modules, config, event reference, known limitations |
| [Smart_Rental_Intelligence_Platform_Overview.pdf](Smart_Rental_Intelligence_Platform_Overview.pdf) | Standalone project-overview writeup |

## Features

**Dashboard**
- Dealer-facing fleet overview: total/out/available/overdue at a glance, live rental status (who has what, checked out when, expected return, color-coded days-left/overdue), available-now quick list
- Full per-vehicle detail table: runtime hours, fuel, idle hours, engine health, return date
- Live equipment map (Leaflet) — auto-fits bounds to the whole fleet, color-codes markers by geofence compliance, draws a dashed line to a non-compliant vehicle's designated location
- Recharts analytics: utilization %, usage per site, fleet utilization pie, fuel usage, revenue estimate

**Rentals**
- Two-step flow enforced by design: check live availability first, then create a *new* customer record, before a rental can be created
- QR code generated per rental; equipment checks out automatically the moment the QR is issued (no extra manual click)
- Check-in via a simulated scan action, returning the vehicle to the available pool

**Intelligence (rule-based, explainable — no black-box ML)**
- Overdue alerts (due-tomorrow + overdue), re-evaluated on every telemetry update
- Demand forecasting: ranks equipment types by historical rental volume per site, plus concrete pre-positioning recommendations (move unit X to site Y, available now/by date Z)
- Anomaly detection: idle hours, unassigned equipment, geofence violations, unexpected movement, fuel anomalies, zero-usage active rentals, degrading engine health — each with severity + recommended action
- Predictive maintenance: 0–100 risk score per vehicle from engine health, tenure duration, idle:runtime ratio, fuel anomalies, geofence non-compliance

**AI Assistant**
- Natural-language chat, routed by a LangGraph orchestrator to one of 5 specialist agents (Fleet, Rental Scheduling, Demand Forecast, Smart Alert, Predictive Maintenance)
- All agent tools are read-only/advisory — no agent can mutate data
- Off-topic questions are recognized and declined instead of hallucinated

**Live data** (`feature/realtime-telemetry-simulator` branch)
- Standalone, physics- and event-driven telemetry simulator — not random jitter. Fuel/engine hours are strictly monotonic, temperature/battery/hydraulics/RPM drift toward realistic targets, GPS follows a heading-based path
- Realistic operating-state duty cycle (RUNNING/IDLE/OFF/MAINTENANCE) and cooldown-gated events (low fuel, overheating, maintenance required, geofence violation, unexpected movement, sensor failure)
- POSTs to the same public API a real IoT device would use — the backend can't tell the difference

## Stack

- **Frontend:** React + TypeScript + Vite, Tailwind CSS, Recharts, Leaflet
- **Backend:** FastAPI (Python), SQLAlchemy + SQLite (Postgres-compatible schema)
- **AI:** LangGraph + LangChain, Groq (Llama 3.3 70B) — one orchestrator agent routing to 5 specialists
- **Live data:** a standalone, physics- and event-driven telemetry simulator (`backend/telemetry_simulator/`) posts realistic real-time telemetry to the REST API every ~10s

## Project structure

```
caterpillarhackathon/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app, lifespan, router registration
│   │   ├── models.py            # SQLAlchemy schema
│   │   ├── schemas.py           # Pydantic request/response models
│   │   ├── seed.py              # Loads the personalized 10-vehicle fleet from the CSV dataset
│   │   ├── agents/               # Orchestrator + 5 specialist agents + tools
│   │   ├── routers/              # One file per REST resource
│   │   └── services/             # Business logic — reused by both routers and agent tools
│   ├── telemetry_simulator/      # Live-data simulator package (feature branch)
│   ├── data/                     # Seed CSV dataset
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   └── src/
│       ├── pages/                # LoginPage, DashboardPage
│       ├── components/           # FleetOverview, AssetMap, RentalsPanel, AgentChat, ...
│       ├── api.ts                # All backend calls
│       └── types.ts              # TS types mirroring backend schemas
├── docs/                         # Detailed documentation (see table above)
└── Smart_Rental_Intelligence_Platform_Overview.pdf
```

## Running locally

### Backend

```bash
cd backend
python -m venv venv
# Windows: venv\Scripts\activate    macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then fill in your own GROQ_API_KEY
python -m uvicorn app.main:app --reload --port 8000
```

The database seeds itself automatically on first run from `backend/data/synthetic_rental_tracking_data.csv`.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Visit the printed local URL and log in with `dealer@rental.com` / `demo123`.

### Telemetry simulator (optional, `feature/realtime-telemetry-simulator` branch)

With the backend running, simulate a realistic real-time IoT feed for the fleet — physics-based fuel/temperature/GPS/engine-health drift, duty-cycle state transitions, and occasional events. Must be run as a module (relative imports):

```bash
cd backend
python -m telemetry_simulator.simulator
python -m telemetry_simulator.simulator --interval 5 --machines 5   # common overrides
```

All tuning lives in `backend/telemetry_simulator/config.py`, overridable via env vars or `backend/.env`. State persists between restarts in `backend/telemetry_simulator_state.json` (gitignored) — delete it to re-bootstrap from the backend's current data. Full details, event reference, and known limitations in [docs/TELEMETRY_SIMULATOR.md](docs/TELEMETRY_SIMULATOR.md).

## Notes

- `backend/.env` (your real API key) is gitignored — use `backend/.env.example` as the template. Never commit a real key.
- The dataset is trimmed to a personalized 10-vehicle fleet; all coordinates are real Indian cities.
- The telemetry simulator lives on its own branch so it can be tried independently — see [docs/TELEMETRY_SIMULATOR.md](docs/TELEMETRY_SIMULATOR.md) for why, and for the couple of known API-contract limitations it surfaces (fuel field units, a few computed-but-not-yet-transmitted fields).
