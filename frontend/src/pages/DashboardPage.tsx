import { useEffect, useState, useCallback, useMemo } from "react";
import Header from "../components/Header";
import AssetTable from "../components/AssetTable";
import AssetMap from "../components/AssetMap";
import FleetOverview from "../components/FleetOverview";
import SummaryCharts from "../components/SummaryCharts";
import AlertsPanel from "../components/AlertsPanel";
import ForecastPanel from "../components/ForecastPanel";
import RentalsPanel from "../components/RentalsPanel";
import AgentChat from "../components/AgentChat";
import { Card } from "../components/ui";
import {
  getEquipment, getRentals, getSummary, getAlerts, getForecast, getAnomalies, getSites,
} from "../api";
import type {
  Equipment, Rental, Summary, Notification, ForecastItem, AnomalyItem, Site,
} from "../types";

const TABS = ["Dashboard", "Rentals & QR", "Summary", "Alerts", "Forecast & Anomalies", "AI Assistant"] as const;
type Tab = (typeof TABS)[number];

export default function DashboardPage({ dealerName }: { dealerName: string }) {
  const [tab, setTab] = useState<Tab>("Dashboard");
  const [equipment, setEquipment] = useState<Equipment[]>([]);
  const [rentals, setRentals] = useState<Rental[]>([]);
  const [sites, setSites] = useState<Site[]>([]);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [alerts, setAlerts] = useState<Notification[]>([]);
  const [forecast, setForecast] = useState<ForecastItem[]>([]);
  const [anomalies, setAnomalies] = useState<AnomalyItem[]>([]);
  const [assetSearch, setAssetSearch] = useState("");

  const refresh = useCallback(async () => {
    const [eq, rent, st, sum, al, fc, an] = await Promise.all([
      getEquipment(), getRentals(), getSites(),
      getSummary(), getAlerts(), getForecast(), getAnomalies(),
    ]);
    setEquipment(eq);
    setRentals(rent);
    setSites(st);
    setSummary(sum);
    setAlerts(al);
    setForecast(fc);
    setAnomalies(an);
  }, []);

  useEffect(() => {
    refresh();
    // Backend simulates a live telemetry tick every ~20s — poll a bit slower
    // than that so the dashboard reliably picks up each new tick.
    const interval = setInterval(refresh, 15000);
    return () => clearInterval(interval);
  }, [refresh]);

  const overdueCount = alerts.filter((a) => a.type === "overdue").length;
  const dueSoonCount = alerts.filter((a) => a.type === "due_soon").length;

  const filteredEquipment = useMemo(() => {
    const q = assetSearch.trim().toLowerCase();
    if (!q) return equipment;
    return equipment.filter(
      (e) =>
        e.equipment_code.toLowerCase().includes(q) ||
        e.type.toLowerCase().includes(q) ||
        e.status.toLowerCase().includes(q) ||
        (e.assigned_site?.site_code ?? "").toLowerCase().includes(q) ||
        (e.assigned_customer?.name ?? "").toLowerCase().includes(q)
    );
  }, [equipment, assetSearch]);

  return (
    <div className="min-h-screen bg-stone-100">
      <Header dealerName={dealerName} onDataChanged={refresh} />

      {(overdueCount > 0 || dueSoonCount > 0) && (
        <div className="bg-red-50 border-b border-red-200 px-6 py-2 text-sm text-red-800">
          {overdueCount > 0 && <span className="font-medium mr-4">{overdueCount} equipment overdue for return</span>}
          {dueSoonCount > 0 && <span className="font-medium">{dueSoonCount} due back tomorrow</span>}
        </div>
      )}

      <nav className="bg-stone-900 px-6 flex gap-1">
        {TABS.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2.5 text-sm font-medium border-b-2 transition ${
              tab === t ? "border-brand-500 text-brand-500" : "border-transparent text-stone-400 hover:text-stone-100"
            }`}
          >
            {t}
          </button>
        ))}
      </nav>

      <main className="p-6 max-w-7xl mx-auto space-y-6">
        {tab === "Dashboard" && (
          <>
            <FleetOverview equipment={equipment} rentals={rentals} />

            <Card className="p-4">
              <h2 className="text-sm font-semibold text-stone-700 mb-3">Live equipment map</h2>
              <AssetMap equipment={equipment} />
            </Card>

            <Card className="p-4">
              <div className="flex items-center justify-between mb-3">
                <h2 className="text-sm font-semibold text-stone-700">
                  Full fleet details <span className="text-stone-400 font-normal">({filteredEquipment.length} of {equipment.length})</span>
                </h2>
                <input
                  type="text"
                  placeholder="Search by code, type, status, site…"
                  className="border border-stone-300 rounded-lg px-3 py-1.5 text-sm w-72"
                  value={assetSearch}
                  onChange={(e) => setAssetSearch(e.target.value)}
                />
              </div>
              <div className="max-h-[32rem] overflow-y-auto">
                <AssetTable equipment={filteredEquipment} />
              </div>
            </Card>
          </>
        )}

        {tab === "Rentals & QR" && (
          <RentalsPanel
            equipment={equipment}
            rentals={rentals}
            sites={sites}
            onChange={refresh}
          />
        )}

        {tab === "Summary" && summary && <SummaryCharts summary={summary} />}

        {tab === "Alerts" && <AlertsPanel alerts={alerts} />}

        {tab === "Forecast & Anomalies" && (
          <div className="space-y-6">
            <div>
              <h2 className="text-sm font-semibold text-stone-700 mb-3">Demand forecast — likely needed next</h2>
              <ForecastPanel forecast={forecast} />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-stone-700 mb-3">Anomaly feed</h2>
              <div className="space-y-2">
                {anomalies.length === 0 && (
                  <Card className="p-4 text-sm text-stone-500">No anomalies detected.</Card>
                )}
                {anomalies.map((a, i) => (
                  <Card key={i} className="p-3">
                    <p className="text-sm text-stone-800">
                      <span className="font-medium">{a.equipment_code}</span> — {a.reason}
                    </p>
                    <p className="text-xs text-stone-500 mt-1">Severity: {a.severity} · {a.recommended_action}</p>
                  </Card>
                ))}
              </div>
            </div>
          </div>
        )}

        {tab === "AI Assistant" && <AgentChat />}
      </main>
    </div>
  );
}
