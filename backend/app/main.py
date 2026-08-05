import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import Base, engine, SessionLocal
from app.seed import seed_if_empty
from app.services import simulator, forecast_service
from app.routers import auth, equipment, customers, sites, rentals, dashboard, agent, telemetry

# Real-time telemetry is driven externally now (the telemetry_simulator
# package -> POST /api/telemetry/report every ~10s). This interval is just
# the safety-net alert/anomaly/maintenance recheck, not telemetry generation.
SAFETY_NET_INTERVAL_SECONDS = 30


async def _safety_net_loop():
    while True:
        await asyncio.sleep(SAFETY_NET_INTERVAL_SECONDS)
        db = SessionLocal()
        try:
            simulator.run_safety_net_checks(db)
        finally:
            db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_if_empty(db)
        simulator.run_safety_net_checks(db)
        forecast_service.run_demand_forecast(db)
    finally:
        db.close()

    task = asyncio.create_task(_safety_net_loop())
    yield
    task.cancel()


app = FastAPI(title="Smart Rental Intelligence Platform", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(equipment.router)
app.include_router(customers.router)
app.include_router(sites.router)
app.include_router(rentals.router)
app.include_router(dashboard.router)
app.include_router(agent.router)
app.include_router(telemetry.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
