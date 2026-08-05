import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend,
} from "recharts";
import type { Summary } from "../types";
import { Card, StatCard } from "./ui";

const COLORS = ["#2563eb", "#f59e0b", "#10b981", "#ef4444", "#8b5cf6", "#06b6d4"];

export default function SummaryCharts({ summary }: { summary: Summary }) {
  const usageData = summary.usage_per_site;
  const utilizationData = [
    { name: "Rented", value: summary.rented_equipment },
    { name: "Available/Idle", value: summary.total_equipment - summary.rented_equipment },
  ];

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard label="Utilization" value={`${summary.utilization_pct}%`} sub={`${summary.rented_equipment}/${summary.total_equipment} rented`} />
        <StatCard label="Total Rented Hours" value={summary.total_rented_hours} />
        <StatCard label="Idle %" value={`${summary.idle_pct}%`} sub={`${summary.total_idle_hours}h idle`} />
        <StatCard label="Revenue Estimate" value={`$${summary.revenue_estimate.toLocaleString()}`} />
      </div>

      <div className="grid md:grid-cols-2 gap-4">
        <Card className="p-4">
          <h3 className="text-sm font-semibold text-slate-700 mb-3">Usage per site (hours)</h3>
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={usageData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis dataKey="site" tick={{ fontSize: 12 }} />
              <YAxis tick={{ fontSize: 12 }} />
              <Tooltip />
              <Bar dataKey="hours" fill="#2563eb" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Card>

        <Card className="p-4">
          <h3 className="text-sm font-semibold text-slate-700 mb-3">Fleet utilization</h3>
          <ResponsiveContainer width="100%" height={240}>
            <PieChart>
              <Pie data={utilizationData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={80} label>
                {utilizationData.map((_, i) => (
                  <Cell key={i} fill={COLORS[i % COLORS.length]} />
                ))}
              </Pie>
              <Legend />
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </Card>
      </div>

      <div className="grid md:grid-cols-3 gap-4">
        <StatCard label="Downtime (available) equipment" value={summary.downtime_equipment} />
        <StatCard label="Total fuel usage" value={`${summary.total_fuel_usage} L`} />
        <StatCard label="Total equipment" value={summary.total_equipment} />
      </div>
    </div>
  );
}
