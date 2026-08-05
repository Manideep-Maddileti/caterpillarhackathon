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
    <div className="sticky top-0 z-10">
      <div className="h-1 bg-brand-500" />
      <header className="bg-white border-b border-stone-200 px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-stone-900 flex items-center justify-center shrink-0">
            <span className="text-brand-500 font-black text-sm tracking-tighter">SR</span>
          </div>
          <div>
            <h1 className="text-base font-semibold text-stone-900 leading-tight">Smart Rental Intelligence Platform</h1>
            <p className="text-xs text-stone-500">Welcome, {dealerName}</p>
          </div>
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
    </div>
  );
}
