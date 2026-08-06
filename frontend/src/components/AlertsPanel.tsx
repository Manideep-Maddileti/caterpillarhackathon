import type { Notification } from "../types";
import { Card, SeverityPill } from "./ui";

const TYPE_LABELS: Record<string, string> = {
  overdue: "Overdue return",
  due_soon: "Due tomorrow",
  anomaly: "Anomaly",
};

export default function AlertsPanel({ alerts }: { alerts: Notification[] }) {
  if (alerts.length === 0) {
    return <Card className="p-4 text-sm text-stone-500">No active alerts.</Card>;
  }
  return (
    <div className="space-y-2">
      {alerts.map((a) => (
        <Card key={a.id} className="p-3 flex items-start justify-between gap-3">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <SeverityPill severity={a.severity} />
              <span className="text-xs font-medium text-stone-500">{TYPE_LABELS[a.type] ?? a.type}</span>
            </div>
            <p className="text-sm text-stone-800">{a.message}</p>
            {a.recommended_action && (
              <p className="text-xs text-stone-500 mt-1">Recommended: {a.recommended_action}</p>
            )}
          </div>
          <span className="text-xs text-stone-400 whitespace-nowrap">
            {new Date(a.created_at).toLocaleString()}
          </span>
        </Card>
      ))}
    </div>
  );
}
