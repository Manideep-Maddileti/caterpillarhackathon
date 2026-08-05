# Smart Rental Intelligence Platform

A dealer-personalized, AI-assisted equipment rental tracking platform for construction &amp; infrastructure fleets. Built for a Caterpillar-style hackathon brief.

Real-time equipment status and GPS tracking, QR-based check-in/check-out, automatic overdue alerts, rule-based demand forecasting and anomaly detection, explainable predictive maintenance scoring, and a conversational multi-agent AI assistant (LangGraph + Groq) — all scoped to a single dealer managing a personalized 10-vehicle fleet across India.

See [Smart_Rental_Intelligence_Platform_Overview.pdf](Smart_Rental_Intelligence_Platform_Overview.pdf) for the full feature and architecture writeup.

## Stack

- **Frontend:** React + TypeScript + Vite, Tailwind CSS, Recharts, Leaflet
- **Backend:** FastAPI (Python), SQLAlchemy + SQLite
- **AI:** LangGraph + LangChain, Groq (Llama 3.3 70B) — one orchestrator agent routing to 5 specialists (Fleet, Rental Scheduling, Demand Forecast, Smart Alert, Predictive Maintenance)
- **Live data:** a standalone Python script posts simulated real-time telemetry to the REST API every ~10s

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

### Live telemetry client (optional)

With the backend running, simulate a real-time IoT feed for the fleet:

```bash
cd backend
python live_telemetry_client.py --interval 10
```

## Notes

- `backend/.env` (your real API key) is gitignored — use `backend/.env.example` as the template.
- The dataset is trimmed to a personalized 10-vehicle fleet; all coordinates are real Indian cities.
