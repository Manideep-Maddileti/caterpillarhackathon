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
    return <Card className="p-4 text-sm text-slate-500">Not enough rental history to forecast yet.</Card>;
  }

  return (
    <div className="grid md:grid-cols-2 gap-4">
      {Object.entries(bySite).map(([site, items]) => (
        <Card key={site} className="p-4">
          <h3 className="text-sm font-semibold text-slate-700 mb-2">{site} — likely needed next</h3>
          <ol className="space-y-1">
            {items.map((f, i) => (
              <li key={f.equipment_type} className="flex justify-between text-sm">
                <span>{i + 1}. {f.equipment_type}</span>
                <span className="text-slate-400">score {f.predicted_demand} ({f.rental_count}x)</span>
              </li>
            ))}
          </ol>
        </Card>
      ))}
    </div>
  );
}
