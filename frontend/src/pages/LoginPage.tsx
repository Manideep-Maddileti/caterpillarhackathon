import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { login } from "../api";
import { Button, Card } from "../components/ui";

export default function LoginPage({ onLogin }: { onLogin: (dealer: { name: string; email: string }) => void }) {
  const [email, setEmail] = useState("dealer@rental.com");
  const [password, setPassword] = useState("demo123");
  const [error, setError] = useState("");
  const navigate = useNavigate();

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    try {
      const data = await login(email, password);
      localStorage.setItem("dealer", JSON.stringify(data));
      onLogin(data);
      navigate("/dashboard");
    } catch {
      setError("Invalid credentials");
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50">
      <Card className="w-full max-w-sm p-8">
        <h1 className="text-xl font-semibold text-slate-900 mb-1">Smart Rental Intelligence</h1>
        <p className="text-sm text-slate-500 mb-6">Dealer login</p>
        <form onSubmit={submit} className="space-y-4">
          <div>
            <label className="text-xs font-medium text-slate-600">Email</label>
            <input
              className="mt-1 w-full border border-slate-300 rounded-lg px-3 py-2 text-sm"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>
          <div>
            <label className="text-xs font-medium text-slate-600">Password</label>
            <input
              type="password"
              className="mt-1 w-full border border-slate-300 rounded-lg px-3 py-2 text-sm"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>
          {error && <p className="text-xs text-red-600">{error}</p>}
          <Button type="submit" className="w-full">Sign in</Button>
        </form>
        <p className="text-xs text-slate-400 mt-4">Demo credentials pre-filled.</p>
      </Card>
    </div>
  );
}
