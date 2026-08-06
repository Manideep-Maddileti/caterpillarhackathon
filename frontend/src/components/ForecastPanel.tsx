import type { ForecastItem } from "../types";
import { Card } from "./ui";

export default function ForecastPanel({ forecast }: { forecast: ForecastItem[] }) {
  const bySite = forecast.reduce<Record<string, ForecastItem[]>>((acc, f) => {
    const key = f.site_code ?? "Unknown site";
    acc[key] = acc[key] ?? [];
    acc[key].push(f);
    return acc;
  }, {});

  if (forecast.length === 0) {
    return <Card className="p-4 text-sm text-stone-500">Not enough rental history to forecast yet.</Card>;
  }

  return (
    <div className="grid md:grid-cols-2 gap-4">
      {Object.entries(bySite).map(([site, items]) => (
        <Card key={site} className="p-4">
          <h3 className="text-sm font-semibold text-stone-700 mb-2">{site} — likely needed next</h3>
          <ol className="space-y-1">
            {items.map((f, i) => (
              <li
                key={f.equipment_type}
                className={`flex justify-between text-sm rounded-md px-2 py-1 -mx-2 ${i === 0 ? "bg-brand-50" : ""}`}
              >
                <span className="flex items-center gap-1.5">
                  {i === 0 && <span className="w-1.5 h-1.5 rounded-full bg-brand-500 shrink-0" />}
                  {i + 1}. {f.equipment_type}
                </span>
                <span className="text-stone-400">score {f.predicted_demand} ({f.rental_count}x)</span>
              </li>
            ))}
          </ol>
        </Card>
      ))}
    </div>
  );
}
