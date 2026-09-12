"use client";

/**
 * Runs a command against /execute and owns the confirm-then-resubmit dance
 * for a destructive action.
 *
 * The user never pre-declares "yes, I might be about to do something
 * destructive" — they submit the command they meant. If the backend comes
 * back with status="blocked" and require_confirmation=true, that's a
 * distinct, actionable state: `pendingConfirm` is set, the caller renders a
 * confirmation affordance, and confirming resubmits the *same* command with
 * confirm_destructive=true. Any other "blocked" is a denial, not a prompt —
 * it's returned as the final response with nothing left to do.
 */

import { useCallback, useState } from "react";
import { executeCommand, type ExecuteResponse } from "@/lib/api";

export function useCommandRunner() {
  const [response, setResponse] = useState<ExecuteResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pendingConfirm, setPendingConfirm] = useState<{
    command: string;
    dryRun: boolean;
  } | null>(null);

  const run = useCallback(async (command: string, dryRun: boolean) => {
    setLoading(true);
    setError(null);
    setPendingConfirm(null);
    try {
      const res = await executeCommand(command, { dry_run: dryRun });
      setResponse(res);
      if (res.status === "blocked" && res.require_confirmation) {
        setPendingConfirm({ command, dryRun });
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  const confirmAndRun = useCallback(async () => {
    if (!pendingConfirm) return;
    const { command, dryRun } = pendingConfirm;
    setLoading(true);
    setError(null);
    try {
      const res = await executeCommand(command, {
        dry_run: dryRun,
        confirm_destructive: true,
      });
      setResponse(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setPendingConfirm(null);
      setLoading(false);
    }
  }, [pendingConfirm]);

  const cancelConfirm = useCallback(() => setPendingConfirm(null), []);

  return { response, loading, error, pendingConfirm, run, confirmAndRun, cancelConfirm };
}
