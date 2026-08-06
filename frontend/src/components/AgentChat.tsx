import { useState, useRef, useEffect } from "react";
import { queryAgent } from "../api";
import { Button, Card } from "./ui";

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  agentUsed?: string;
  agentKey?: string;
}

const SUGGESTIONS = [
  "Which equipment is outside its designated geofence?",
  "What equipment needs maintenance soon?",
  "What excavators are available to rent at S004?",
  "Which equipment types are most needed at S009?",
  "Are there any overdue rentals?",
];

const AGENT_BADGE_COLORS: Record<string, string> = {
  fleet: "bg-blue-100 text-blue-700",
  rental_scheduling: "bg-purple-100 text-purple-700",
  demand_forecast: "bg-emerald-100 text-emerald-700",
  smart_alert: "bg-amber-100 text-amber-700",
  predictive_maintenance: "bg-red-100 text-red-700",
};

export default function AgentChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      role: "assistant",
      content:
        "Hi, I'm the platform's AI assistant. I route your question to the right specialist — Fleet, Rental Scheduling, Demand Forecast, Smart Alert, or Predictive Maintenance. Ask me anything about the fleet.",
    },
  ]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const send = async (text: string) => {
    const message = text.trim();
    if (!message || busy) return;
    setMessages((m) => [...m, { role: "user", content: message }]);
    setInput("");
    setBusy(true);
    try {
      const result = await queryAgent(message);
      setMessages((m) => [
        ...m,
        { role: "assistant", content: result.response, agentUsed: result.agent_used, agentKey: result.agent_key },
      ]);
    } catch {
      setMessages((m) => [...m, { role: "assistant", content: "Sorry, something went wrong reaching the agent." }]);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card className="p-4 flex flex-col h-[36rem]">
      <div className="flex-1 overflow-y-auto space-y-3 pr-1">
        {messages.map((m, i) => (
          <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
            <div
              className={`max-w-[80%] rounded-lg px-3 py-2 text-sm ${
                m.role === "user" ? "bg-blue-600 text-white" : "bg-slate-100 text-slate-800"
              }`}
            >
              {m.agentUsed && (
                <span
                  className={`inline-block text-[10px] font-semibold uppercase tracking-wide rounded-full px-2 py-0.5 mb-1 ${
                    AGENT_BADGE_COLORS[m.agentKey ?? ""] ?? "bg-slate-200 text-slate-700"
                  }`}
                >
                  {m.agentUsed}
                </span>
              )}
              <p className="whitespace-pre-wrap">{m.content}</p>
            </div>
          </div>
        ))}
        {busy && (
          <div className="flex justify-start">
            <div className="bg-slate-100 text-slate-500 rounded-lg px-3 py-2 text-sm">Thinking…</div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {messages.length <= 1 && (
        <div className="flex flex-wrap gap-2 mb-3">
          {SUGGESTIONS.map((s) => (
            <button
              key={s}
              onClick={() => send(s)}
              className="text-xs bg-slate-100 hover:bg-slate-200 text-slate-600 rounded-full px-3 py-1.5"
            >
              {s}
            </button>
          ))}
        </div>
      )}

      <form
        onSubmit={(e) => {
          e.preventDefault();
          send(input);
        }}
        className="flex gap-2 pt-2 border-t border-slate-200"
      >
        <input
          className="flex-1 border border-slate-300 rounded-lg px-3 py-2 text-sm"
          placeholder="Ask about equipment, alerts, forecasts, maintenance…"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          disabled={busy}
        />
        <Button type="submit" disabled={busy || !input.trim()}>Send</Button>
      </form>
    </Card>
  );
}
