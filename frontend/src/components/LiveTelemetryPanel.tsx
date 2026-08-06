import { useEffect, useRef, useState } from "react";
import type { Equipment } from "../types";
import { Card, StatusBadge } from "./ui";

// engine_health is derived server-side from idle_hours on every telemetry
// tick (see telemetry_ingest.py) — these bands mirror the thresholds the
// backend's anomaly/maintenance services already use, so a card reads
// "at risk" here exactly when the AI agents would also flag it.
function healthTone(health: number) {
  if (health >= 85) return { bar: "bg-emerald-500", text: "text-emerald-700", label: "Healthy" };
  if (health >= 70) return { bar: "bg-orange-400", text: "text-orange-700", label: "Watch" };
  return { bar: "bg-red-500", text: "text-red-700", label: "At risk" };
}

export default function LiveTelemetryPanel({ equipment }: { equipment: Equipment[] }) {
  // Only machines actually out with a customer generate telemetry worth
  // watching live — idle yard stock doesn't need a card here.
  const rentedEquipment = equipment.filter((e) => e.status !== "available");

  // Flags a card as "just updated" for a moment when its live fields change
  // between polls — the only visible signal (short of a websocket) that a
  // new telemetry tick from the simulator actually landed for that machine.
  const [pulsing, setPulsing] = useState<Set<number>>(new Set());
  const prevRef = useRef<Map<number, string>>(new Map());

  useEffect(() => {
    const prev = prevRef.current;
    const changed = new Set<number>();
    for (const e of rentedEquipment) {
      const snapshot = `${e.fuel_usage}|${e.runtime_hours}|${e.idle_hours}|${e.engine_health}|${e.gps_lat}|${e.gps_lng}`;
      if (prev.has(e.id) && prev.get(e.id) !== snapshot) changed.add(e.id);
      prev.set(e.id, snapshot);
    }
    if (changed.size > 0) {
      setPulsing(changed);
      const t = setTimeout(() => setPulsing(new Set()), 2000);
      return () => clearTimeout(t);
    }
  }, [rentedEquipment]);

  return (
    <Card className="p-4">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-sm font-semibold text-stone-700">Live telemetry</h2>
        <span className="flex items-center gap-1.5 text-xs text-stone-400">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
          Updates as each machine reports in
        </span>
      </div>
      {rentedEquipment.length === 0 ? (
        <p className="text-sm text-stone-500">Nothing is out on rent right now — no live telemetry to show.</p>
      ) : (
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
        {rentedEquipment.map((e) => {
          const tone = healthTone(e.engine_health);
          const isPulsing = pulsing.has(e.id);
          return (
            <div
              key={e.id}
              className={`border rounded-lg p-3 transition-colors ${
                isPulsing ? "border-brand-400 bg-brand-50" : "border-stone-200"
              }`}
            >
              <div className="flex items-center justify-between mb-1">
                <span className="text-sm font-semibold text-stone-900">{e.equipment_code}</span>
                <StatusBadge status={e.status} />
              </div>
              <p className="text-xs text-stone-400 mb-2">{e.type}</p>

              <div className="flex items-center justify-between text-xs mb-1">
                <span className="text-stone-500">Engine health</span>
                <span className={`font-medium ${tone.text}`}>{e.engine_health.toFixed(0)}% · {tone.label}</span>
              </div>
              <div className="h-1.5 rounded-full bg-stone-100 overflow-hidden mb-2">
                <div className={`h-full ${tone.bar}`} style={{ width: `${Math.min(100, e.engine_health)}%` }} />
              </div>

              <div className="grid grid-cols-3 gap-1 text-center">
                <div>
                  <p className="text-xs font-semibold text-stone-800">{e.fuel_usage.toFixed(1)}</p>
                  <p className="text-[10px] text-stone-400">L/day fuel</p>
                </div>
                <div>
                  <p className="text-xs font-semibold text-stone-800">{e.runtime_hours.toFixed(1)}</p>
                  <p className="text-[10px] text-stone-400">runtime h</p>
                </div>
                <div>
                  <p className="text-xs font-semibold text-stone-800">{e.idle_hours.toFixed(1)}</p>
                  <p className="text-[10px] text-stone-400">idle h</p>
                </div>
              </div>
            </div>
          );
        })}
      </div>
      )}
    </Card>
  );
}
