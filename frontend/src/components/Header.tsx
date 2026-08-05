import { useNavigate } from "react-router-dom";
import { Button } from "./ui";

export default function Header({
  dealerName, onDataChanged,
}: {
  dealerName: string;
  onDataChanged: () => void;
}) {
  const navigate = useNavigate();

  const logout = () => {
    localStorage.removeItem("dealer");
    navigate("/login");
  };

  return (
    <header className="bg-white border-b border-slate-200 px-6 py-3 flex items-center justify-between sticky top-0 z-10">
      <div>
        <h1 className="text-base font-semibold text-slate-900">Smart Rental Intelligence Platform</h1>
        <p className="text-xs text-slate-500">Welcome, {dealerName}</p>
      </div>
      <div className="flex items-center gap-3">
        <span className="flex items-center gap-1.5 text-xs font-medium text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-full px-2.5 py-1">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
          Live telemetry
        </span>
        <Button variant="secondary" onClick={onDataChanged}>Refresh</Button>
        <Button variant="danger" onClick={logout}>Logout</Button>
      </div>
    </header>
  );
}
