import type { Equipment, Rental } from "../types";
import { Card, StatCard } from "./ui";

function daysBetween(a: Date, b: Date) {
  return Math.round((a.getTime() - b.getTime()) / (1000 * 60 * 60 * 24));
}

export default function FleetOverview({ equipment, rentals }: { equipment: Equipment[]; rentals: Rental[] }) {
  const total = equipment.length;
  const rented = equipment.filter((e) => e.status === "rented");
  const overdue = equipment.filter((e) => e.status === "overdue");
  const available = equipment.filter((e) => e.status === "available");
  const outNow = [...rented, ...overdue];

  const activeRentalFor = (equipmentId: number) =>
    rentals.find((r) => r.equipment_id === equipmentId && r.status === "active");

  const now = new Date();

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard label="Total Fleet" value={total} />
        <StatCard
          label="Out On Rent"
          value={outNow.length}
          sub={`${rented.length} on-time, ${overdue.length} overdue`}
        />
        <StatCard label="Available Now" value={available.length} />
        <StatCard label="Overdue" value={overdue.length} />
      </div>

      <Card className="p-4">
        <h3 className="text-sm font-semibold text-stone-700 mb-3">Currently rented — live status</h3>
        {outNow.length === 0 ? (
          <p className="text-sm text-stone-500">Nothing is out right now — the whole fleet is available.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="text-left text-xs uppercase tracking-wide text-stone-500 border-b border-stone-200">
                  <th className="py-2 pr-4">Equipment</th>
                  <th className="py-2 pr-4">Customer</th>
                  <th className="py-2 pr-4">Checked out</th>
                  <th className="py-2 pr-4">Expected return</th>
                  <th className="py-2 pr-4">Status</th>
                </tr>
              </thead>
              <tbody>
                {outNow.map((e) => {
                  const rental = activeRentalFor(e.id);
                  const returnDate = e.return_date ? new Date(e.return_date) : null;
                  const diff = returnDate ? daysBetween(returnDate, now) : null;
                  return (
                    <tr key={e.id} className="border-b border-stone-100">
                      <td className="py-2 pr-4 font-medium">
                        {e.equipment_code} <span className="text-stone-400 font-normal">({e.type})</span>
                      </td>
                      <td className="py-2 pr-4">{e.assigned_customer?.name ?? "—"}</td>
                      <td className="py-2 pr-4">
                        {rental?.check_in_date ? new Date(rental.check_in_date).toLocaleDateString() : "—"}
                      </td>
                      <td className="py-2 pr-4">{returnDate ? returnDate.toLocaleDateString() : "—"}</td>
                      <td className="py-2 pr-4">
                        {e.status === "overdue" ? (
                          <span className="text-red-600 font-medium">
                            Overdue by {Math.abs(diff ?? 0)} day{Math.abs(diff ?? 0) === 1 ? "" : "s"}
                          </span>
                        ) : diff !== null && diff <= 1 ? (
                          <span className="text-orange-600 font-medium">Due {diff <= 0 ? "today" : "tomorrow"}</span>
                        ) : (
                          <span className="text-emerald-600 font-medium">{diff} days left</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <Card className="p-4">
        <h3 className="text-sm font-semibold text-stone-700 mb-3">Available now</h3>
        {available.length === 0 ? (
          <p className="text-sm text-stone-500">Everything is currently rented out.</p>
        ) : (
          <div className="flex flex-wrap gap-2">
            {available.map((e) => (
              <span
                key={e.id}
                className="text-sm bg-emerald-50 text-emerald-700 border border-emerald-200 rounded-lg px-3 py-1.5"
              >
                {e.equipment_code} — {e.type}
                {e.assigned_site ? ` · ${e.assigned_site.site_code}` : ""}
              </span>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
