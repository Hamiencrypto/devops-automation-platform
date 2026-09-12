"use client";

import { useEffect, useState } from "react";
import { ArrowRight, FlaskConical, Loader2 } from "lucide-react";

interface Props {
  onExecute: (command: string, dryRun: boolean) => Promise<void>;
  loading: boolean;
  compact?: boolean;
  initialValue?: string;
}

const SAMPLE_COMMANDS = [
  "deploy nginx on port 8080",
  "list all containers",
  "system health",
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

  // Keep internal state in sync when parent passes a new prompt
  useEffect(() => {
    if (initialValue !== undefined) setCommand(initialValue);
  }, [initialValue]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!command.trim()) return;
    await onExecute(command, dryRun);
  }

  return (
    <div className={"card " + (compact ? "p-3" : "p-4")}>
      <form onSubmit={handleSubmit}>
        <label htmlFor="command-input" className="label-caps mb-1.5 block">
          Command
        </label>
        <div className="flex gap-2">
          <input
            id="command-input"
            type="text"
            value={command}
            onChange={(e) => setCommand(e.target.value)}
            placeholder='e.g. "deploy nginx on port 8080" or "stop abc123"'
            className="input font-mono text-sm py-2.5"
            disabled={loading}
            autoComplete="off"
            spellCheck={false}
          />
          <button
            type="submit"
            className="btn-primary px-4 shrink-0"
            disabled={loading || !command.trim()}
          >
            {loading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <>
                Run
                <ArrowRight className="h-3.5 w-3.5" />
              </>
            )}
          </button>
        </div>

        <label className="mt-2.5 flex w-fit items-center gap-1.5 text-xs text-zinc-500 dark:text-zinc-400 cursor-pointer select-none">
          <input
            type="checkbox"
            checked={dryRun}
            onChange={(e) => setDryRun(e.target.checked)}
            className="rounded accent-zinc-900 dark:accent-zinc-100"
          />
          <FlaskConical className="h-3.5 w-3.5" />
          Dry run — plan only, don&apos;t execute
        </label>
      </form>

      {!compact && (
        <div className="mt-3 pt-3 border-t border-zinc-200 dark:border-zinc-800">
          <p className="label-caps mb-2">Try one of these</p>
          <div className="flex flex-wrap gap-1.5">
            {SAMPLE_COMMANDS.map((sample) => (
              <button
                key={sample}
                onClick={() => setCommand(sample)}
                className="rounded px-2 py-1 font-mono text-xs text-zinc-600 bg-zinc-100
                           hover:bg-zinc-200 hover:text-zinc-900 transition-colors
                           dark:text-zinc-400 dark:bg-zinc-800 dark:hover:bg-zinc-700 dark:hover:text-zinc-100"
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
