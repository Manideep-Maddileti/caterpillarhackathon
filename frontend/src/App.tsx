import { useState } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import LoginPage from "./pages/LoginPage";
import DashboardPage from "./pages/DashboardPage";

interface Dealer {
  name: string;
  email: string;
}

function loadDealer(): Dealer | null {
  const raw = localStorage.getItem("dealer");
  return raw ? JSON.parse(raw) : null;
}

export default function App() {
  const [dealer, setDealer] = useState<Dealer | null>(loadDealer());

  return (
    <BrowserRouter>
      <Routes>
        <Route
          path="/login"
          element={<LoginPage onLogin={(d) => setDealer(d)} />}
        />
        <Route
          path="/dashboard"
          element={dealer ? <DashboardPage dealerName={dealer.name} /> : <Navigate to="/login" replace />}
        />
        <Route path="*" element={<Navigate to={dealer ? "/dashboard" : "/login"} replace />} />
      </Routes>
    </BrowserRouter>
  );
}
