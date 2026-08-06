import type { Equipment } from "../types";
import { StatusBadge } from "./ui";

export default function AssetTable({ equipment }: { equipment: Equipment[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="min-w-full text-sm">
        <thead>
          <tr className="text-left text-xs uppercase tracking-wide text-slate-500 border-b border-slate-200">
            <th className="py-2 pr-4">Equipment</th>
            <th className="py-2 pr-4">Type</th>
            <th className="py-2 pr-4">Status</th>
            <th className="py-2 pr-4">Customer</th>
            <th className="py-2 pr-4">Site</th>
            <th className="py-2 pr-4">Runtime h</th>
            <th className="py-2 pr-4">Fuel</th>
            <th className="py-2 pr-4">Idle h</th>
            <th className="py-2 pr-4">Engine health</th>
            <th className="py-2 pr-4">Return date</th>
          </tr>
        </thead>
        <tbody>
          {equipment.map((e) => (
            <tr key={e.id} className="border-b border-slate-100 hover:bg-slate-50">
              <td className="py-2 pr-4 font-medium text-slate-900">{e.equipment_code}</td>
              <td className="py-2 pr-4">{e.type}</td>
              <td className="py-2 pr-4"><StatusBadge status={e.status} /></td>
              <td className="py-2 pr-4">{e.assigned_customer?.name ?? "—"}</td>
              <td className="py-2 pr-4">{e.assigned_site?.site_code ?? "Unassigned"}</td>
              <td className="py-2 pr-4">{e.runtime_hours}</td>
              <td className="py-2 pr-4">{e.fuel_usage}</td>
              <td className="py-2 pr-4">{e.idle_hours}</td>
              <td className="py-2 pr-4">{e.engine_health.toFixed(0)}%</td>
              <td className="py-2 pr-4">{e.return_date ? new Date(e.return_date).toLocaleDateString() : "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
