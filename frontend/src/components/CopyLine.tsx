export default function CopyLine({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="mb-1 text-xs font-medium text-slate-500">{label}</p>
      <div className="flex items-center gap-2">
        <code className="min-w-0 flex-1 break-all font-mono text-sm text-slate-900">{value}</code>
        <button
          onClick={() => navigator.clipboard.writeText(value)}
          className="whitespace-nowrap text-xs font-medium text-slate-700 hover:text-slate-950"
        >
          Copy
        </button>
      </div>
    </div>
  );
}
