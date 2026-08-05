# API Reference

Base URL (local dev): `http://127.0.0.1:8000`

All request/response bodies are JSON. Interactive docs (Swagger UI) are also available at `/docs` whenever the backend is running.

## Auth

### `POST /api/auth/login`
Hardcoded single-dealer login (hackathon scope — not real auth).

**Request**
```json
{ "email": "dealer@rental.com", "password": "demo123" }
```

## Equipment

### `GET /api/equipment`
List the full fleet. Each item includes nested `assigned_customer`, `assigned_site`, and `tenure` (designated coordinates + compliance) objects.

### `GET /api/equipment/{equipment_id}`
One equipment by internal numeric id.

### `POST /api/equipment`
Create a new equipment record.
```json
{ "equipment_code": "EQX1099", "name": "Optional name", "type": "Excavator", "assigned_site_id": 1 }
```

## Customers

### `GET /api/customers`
List all customers.

### `POST /api/customers`
Create a customer — required before a rental can be created for them.
```json
{ "name": "Acme Construction", "company": "Acme Infra Pvt Ltd", "contact": "acme@example.com" }
```

## Sites

### `GET /api/sites`
List all sites (site_code, name, lat, lng).

### `POST /api/sites`
Create a site.
```json
{ "site_code": "S013", "name": "Site S013", "lat": 12.97, "lng": 77.59 }
```

## Rentals

### `GET /api/rentals`
List all rentals (created / active / completed), most recent first.

### `POST /api/rentals`
Create a rental. Generates a QR code (returned as a base64 PNG data URL in `qr_code`). Status starts as `"created"`.
```json
{ "equipment_id": 3, "customer_id": 7, "site_id": 2, "rental_days": 7 }
```

### `POST /api/rentals/{rental_id}/checkout`
Marks the rental `"active"` and the equipment `"rented"`.

### `POST /api/rentals/{rental_id}/checkin`
Marks the rental `"completed"` and frees the equipment back to `"available"`.

## Dashboard & analytics

### `GET /api/dashboard/summary`
Fleet-wide stats: utilization %, total rented/idle hours, idle %, downtime equipment count, fuel usage, usage-per-site breakdown, revenue estimate.

### `GET /api/alerts`
The unified notification feed (`type` ∈ `overdue`, `due_soon`, `anomaly`, `maintenance`), sorted by severity then recency.

### `POST /api/alerts/refresh`
Manually re-runs the overdue check + anomaly scan and returns counts. (Not required for normal operation — both already re-run automatically on every telemetry update and every 30s as a safety net.)

### `GET /api/forecast`
Rule-based demand ranking: equipment type × site, ranked by historical rental-day volume.

### `GET /api/anomalies`
Runs a fresh anomaly scan and returns findings: `{equipment_code, reason, severity, recommended_action}` per issue found (idle hours, unassigned equipment, geofence violations, fuel anomalies, zero-usage active rentals, degrading engine health).

### `GET /api/maintenance`
Runs a fresh predictive-maintenance scan: `{equipment_code, risk_score (0-100), risk_level, reasons[], recommended_action}` per equipment, sorted highest-risk first.

## AI Agent

### `POST /api/agent/query`
Natural-language question, routed by the orchestrator to one of five specialist agents (or a polite decline if out of scope). See [AI_AGENTS.md](AI_AGENTS.md).

**Request**
```json
{ "message": "Which equipment is outside its designated geofence?" }
```

**Response**
```json
{
  "response": "There are no equipment outside their designated geofence.",
  "agent_used": "Fleet Agent",
  "agent_key": "fleet"
}
```

## Telemetry ingestion

### `POST /api/telemetry/report`
Ingests one live reading for one equipment — this is the endpoint the telemetry simulator (or, eventually, real hardware) calls. Updates the equipment row, inserts a `telemetry` history row, and immediately re-runs overdue/anomaly/maintenance checks.

**Request** — every field except `equipment_code` is optional (a reading can update just a subset of fields):
```json
{
  "equipment_code": "EQX1001",
  "lat": 13.0827,
  "lng": 80.2707,
  "fuel_usage": 42.5,
  "runtime_hours": 5.3,
  "idle_hours": 1.1
}
```

> **Known limitation:** `fuel_usage` is historically litres/day in this schema, not a 0–100% gauge. The telemetry simulator's internal fuel model is percentage-based and writes directly into this field as a stopgap — see [TELEMETRY_SIMULATOR.md](TELEMETRY_SIMULATOR.md) for the full explanation. There's also currently no field for engine temperature, battery voltage, hydraulic pressure, RPM, or engine operating state (RUNNING/IDLE/OFF/MAINTENANCE) — the simulator computes all of these internally but the live API has nowhere to put them yet.

## Health

### `GET /api/health`
Plain liveness check, `{"status": "ok"}`.
