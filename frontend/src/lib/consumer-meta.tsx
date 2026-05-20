export const CONSUMER_COLORS: Record<string, string> = {
  "Claude Code": "bg-amber-50 text-amber-800 border border-amber-200",
  "Codex": "bg-sky-50 text-sky-800 border border-sky-200",
  "Copilot": "bg-emerald-50 text-emerald-800 border border-emerald-200",
};

export function ConsumerBadge({ consumer }: { consumer: string }) {
  return (
    <span className={`rounded px-1.5 py-0.5 text-xs ${CONSUMER_COLORS[consumer] ?? "bg-slate-100 text-slate-600"}`}>
      {consumer}
    </span>
  );
}
