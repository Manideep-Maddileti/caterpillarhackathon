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
    <div className="min-h-screen flex items-center justify-center bg-stone-900 relative overflow-hidden">
      <div className="absolute -top-24 -right-24 w-96 h-96 bg-brand-500/10 rounded-full blur-3xl" />
      <div className="absolute -bottom-24 -left-24 w-96 h-96 bg-brand-500/10 rounded-full blur-3xl" />

      <div className="relative z-10 flex flex-col items-center">
        <div className="w-14 h-14 rounded-xl bg-brand-500 flex items-center justify-center mb-6 shadow-lg shadow-brand-500/20">
          <span className="text-stone-900 font-black text-xl tracking-tighter">SR</span>
        </div>

        <Card className="w-full max-w-sm p-8 border-t-4 border-t-brand-500">
          <h1 className="text-xl font-semibold text-stone-900 mb-1">Smart Rental Intelligence</h1>
          <p className="text-sm text-stone-500 mb-6">Dealer login</p>
          <form onSubmit={submit} className="space-y-4">
            <div>
              <label className="text-xs font-medium text-stone-600">Email</label>
              <input
                className="mt-1 w-full border border-stone-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-400 focus:border-brand-400"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </div>
            <div>
              <label className="text-xs font-medium text-stone-600">Password</label>
              <input
                type="password"
                className="mt-1 w-full border border-stone-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-400 focus:border-brand-400"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </div>
            {error && <p className="text-xs text-red-600">{error}</p>}
            <Button type="submit" className="w-full">Sign in</Button>
          </form>
          <p className="text-xs text-stone-400 mt-4">Demo credentials pre-filled.</p>
        </Card>
      </div>
    </div>
  );
}
