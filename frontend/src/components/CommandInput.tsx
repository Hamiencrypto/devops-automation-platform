"use client";

import { useEffect, useState } from "react";
import { Play, TestTube2, AlertTriangle, Loader2, Terminal } from "lucide-react";

interface Props {
  onExecute: (
    command: string,
    opts: { dry_run: boolean; confirm_destructive: boolean }
  ) => Promise<void>;
  loading: boolean;
  compact?: boolean;
  initialValue?: string;
}

const SAMPLE_COMMANDS = [
  "deploy nginx on port 8080",
  "deploy rabbitmq",
  "deploy mongodb",
  "list all containers",
  "system health",
  "disk usage",
  "analyze logs at /data/sample.log",
  "count lines in package.json",
];

export default function CommandInput({
  onExecute,
  loading,
  compact,
  initialValue,
}: Props) {
  const [command, setCommand] = useState(initialValue ?? "");
  const [dryRun, setDryRun] = useState(false);
  const [confirmDestructive, setConfirmDestructive] = useState(false);

  // Keep internal state in sync when parent passes a new prompt
  useEffect(() => {
    if (initialValue !== undefined) setCommand(initialValue);
  }, [initialValue]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!command.trim()) return;
    await onExecute(command, {
      dry_run: dryRun,
      confirm_destructive: confirmDestructive,
    });
  }

  return (
    <div className={"card hero-glow relative " + (compact ? "p-4" : "p-6")}>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="flex items-center gap-2 text-sm font-medium heading mb-2">
            <Terminal className="h-4 w-4 text-brand-500" />
            Natural Language Command
          </label>
          <div className="flex gap-2">
            <input
              type="text"
              value={command}
              onChange={(e) => setCommand(e.target.value)}
              placeholder='Try: "deploy nginx on port 8080" or "stop abc123"'
              className="input text-base py-3"
              disabled={loading}
            />
            <button
              type="submit"
              className="btn-primary px-5"
              disabled={loading || !command.trim()}
            >
              {loading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <>
                  <Play className="h-4 w-4" />
                  Execute
                </>
              )}
            </button>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-4">
          <label className="flex items-center gap-2 text-sm muted cursor-pointer">
            <input
              type="checkbox"
              checked={dryRun}
              onChange={(e) => setDryRun(e.target.checked)}
              className="rounded accent-brand-500"
            />
            <TestTube2 className="h-4 w-4 text-amber-500" />
            Dry-run mode (plan only, don&apos;t execute)
          </label>
          <label className="flex items-center gap-2 text-sm muted cursor-pointer">
            <input
              type="checkbox"
              checked={confirmDestructive}
              onChange={(e) => setConfirmDestructive(e.target.checked)}
              className="rounded accent-red-500"
            />
            <AlertTriangle className="h-4 w-4 text-red-500" />
            Confirm destructive actions
          </label>
        </div>
      </form>

      {!compact && (
        <div className="mt-4 pt-4 border-t border-slate-200 dark:border-slate-800">
          <p className="text-xs font-medium muted mb-2 tracking-wider">
            QUICK EXAMPLES
          </p>
          <div className="flex flex-wrap gap-2">
            {SAMPLE_COMMANDS.map((sample) => (
              <button
                key={sample}
                onClick={() => setCommand(sample)}
                className="text-xs px-3 py-1.5 rounded-md
                           bg-slate-100 text-slate-700 hover:bg-brand-100 hover:text-brand-700
                           dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-brand-500/15
                           dark:hover:text-brand-300 transition"
                type="button"
              >
                {sample}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
