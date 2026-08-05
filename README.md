# Smart Rental Intelligence Platform

A dealer-personalized, AI-assisted equipment rental tracking platform for construction &amp; infrastructure fleets. Built for a Caterpillar-style hackathon brief.

Real-time equipment status and GPS tracking, QR-based check-in/check-out, automatic overdue alerts, rule-based demand forecasting and anomaly detection, explainable predictive maintenance scoring, and a conversational multi-agent AI assistant (LangGraph + Groq) — all scoped to a single dealer managing a personalized 10-vehicle fleet across India.

See [Smart_Rental_Intelligence_Platform_Overview.pdf](Smart_Rental_Intelligence_Platform_Overview.pdf) for the full feature and architecture writeup.

## Stack

- **Frontend:** React + TypeScript + Vite, Tailwind CSS, Recharts, Leaflet
- **Backend:** FastAPI (Python), SQLAlchemy + SQLite
- **AI:** LangGraph + LangChain, Groq (Llama 3.3 70B) — one orchestrator agent routing to 5 specialists (Fleet, Rental Scheduling, Demand Forecast, Smart Alert, Predictive Maintenance)
- **Live data:** a standalone, physics- and event-driven telemetry simulator (`backend/telemetry_simulator/`) posts realistic real-time telemetry to the REST API every ~10s

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

### Telemetry simulator (optional)

With the backend running, simulate a realistic real-time IoT feed for the fleet — physics-based fuel/temperature/GPS/engine-health drift, duty-cycle state transitions (RUNNING/IDLE/OFF/MAINTENANCE), and occasional events (low fuel, overheating, maintenance required, geofence violation, unexpected movement, sensor failure). Must be run as a module (relative imports):

```bash
cd backend
python -m telemetry_simulator.simulator
python -m telemetry_simulator.simulator --interval 5 --machines 5   # common overrides
```

All tuning (rates, thresholds, event probabilities, feature flags) lives in `backend/telemetry_simulator/config.py`, overridable via env vars or `backend/.env`. State persists between restarts in `backend/telemetry_simulator_state.json` (gitignored) — delete it to re-bootstrap from the backend's current data.

## Notes

- `backend/.env` (your real API key) is gitignored — use `backend/.env.example` as the template.
- The dataset is trimmed to a personalized 10-vehicle fleet; all coordinates are real Indian cities.
