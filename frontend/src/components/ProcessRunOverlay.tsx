import { createPortal } from "react-dom";
import {
  AlertTriangle,
  Box,
  Check,
  Cpu,
  FilePenLine,
  GitBranch,
  History,
  Inbox,
  Radar,
  ShieldCheck,
  Sparkles,
  UserCheck,
  X,
} from "lucide-react";
import { Button } from "./ui";

export type RunEvent = {
  sequence?: number;
  event_type?: string;
  message?: string;
  timestamp?: string;
  payload?: Record<string, unknown>;
};

const STAGES = [
  {
    id: "intake",
    label: "Intake",
    hint: "Receive and normalize the ticket",
    icon: Inbox,
    events: ["TICKET_RECEIVED", "TICKET_NORMALIZED"],
  },
  {
    id: "interpret",
    label: "Interpretation",
    hint: "Extract structured change intent",
    icon: Sparkles,
    events: ["AI_INTERPRETATION_STARTED", "AI_INTERPRETATION_COMPLETED"],
  },
  {
    id: "resolve",
    label: "Rule resolution",
    hint: "Market-Brand › Brand › Market › Universal",
    icon: GitBranch,
    events: ["RULE_SEARCH_STARTED", "TARGET_RULE_SELECTED", "CURRENT_RULE_RETRIEVED", "RULE_NOT_FOUND"],
  },
  {
    id: "propose",
    label: "Proposal",
    hint: "Draft typed operations on a copy",
    icon: FilePenLine,
    events: ["PROPOSAL_CREATED"],
  },
  {
    id: "validate",
    label: "Validation",
    hint: "Schema, citations, scope, conflicts",
    icon: ShieldCheck,
    events: ["VALIDATION_STARTED", "VALIDATOR_RESULT", "VALIDATION_COMPLETED", "VALIDATION_FAILED"],
  },
  {
    id: "sandbox",
    label: "Sandbox",
    hint: "Isolate proposed version from production",
    icon: Box,
    events: ["SANDBOX_CREATED"],
  },
  {
    id: "replay",
    label: "Historical replay",
    hint: "Execute production vs proposed on reviews",
    icon: History,
    events: ["HISTORICAL_REPLAY_STARTED", "REGRESSION_COMPLETED", "REGRESSION_FAILED"],
  },
  {
    id: "impact",
    label: "Impact",
    hint: "Blast radius across market and brand",
    icon: Radar,
    events: ["IMPACT_COMPLETED"],
  },
  {
    id: "risk",
    label: "Risk",
    hint: "Policy gate and overall score",
    icon: AlertTriangle,
    events: ["RISK_CALCULATED"],
  },
  {
    id: "approval",
    label: "Approval gate",
    hint: "Queue for MLR admin sign-off",
    icon: UserCheck,
    events: ["APPROVAL_REQUESTED", "NEEDS_CLARIFICATION"],
  },
] as const;

const FAIL_EVENTS = new Set([
  "VALIDATION_FAILED",
  "REGRESSION_FAILED",
  "RULE_NOT_FOUND",
  "NEEDS_CLARIFICATION",
]);

type StageState = "pending" | "running" | "done" | "fail";

function stageState(stageEvents: readonly string[], seen: Set<string>, running: boolean): StageState {
  const hit = stageEvents.filter((e) => seen.has(e));
  if (hit.some((e) => FAIL_EVENTS.has(e))) return "fail";
  const terminals = stageEvents.filter((e) => !e.endsWith("_STARTED") && e !== "VALIDATOR_RESULT");
  if (terminals.some((e) => seen.has(e))) return "done";
  if (hit.length || (running && stageEvents.some((e) => seen.has(e)))) return "running";
  return "pending";
}

function firstPendingIndex(states: StageState[]) {
  const running = states.findIndex((s) => s === "running" || s === "fail");
  if (running >= 0) return running;
  const pending = states.findIndex((s) => s === "pending");
  return pending < 0 ? states.length - 1 : pending;
}

export function ProcessRunOverlay({
  open,
  ticketNumber,
  title,
  events,
  pending,
  error,
  execMode,
  onClose,
}: {
  open: boolean;
  ticketNumber?: string;
  title?: string;
  events: RunEvent[];
  pending: boolean;
  error?: string | null;
  execMode?: string | null;
  onClose: () => void;
}) {
  if (!open || typeof document === "undefined") return null;

  const seen = new Set(events.map((e) => e.event_type || ""));
  const states = STAGES.map((s, i, all) => {
    let st = stageState(s.events, seen, pending);
    if (st === "pending" && pending) {
      const prevDone = i === 0 || ["done", "fail"].includes(stageState(all[i - 1].events, seen, pending));
      const laterHit = all.slice(i + 1).some((n) => n.events.some((ev) => seen.has(ev)));
      if (prevDone && !laterHit) st = "running";
    }
    return st;
  });
  const active = firstPendingIndex(states);
  const doneCount = states.filter((s) => s === "done").length;
  const failed = states.some((s) => s === "fail") || Boolean(error);
  const complete = !pending && !error;
  const pct = Math.round((doneCount / STAGES.length) * 100);
  const latest = events[events.length - 1];
  const headline = failed
    ? latest?.message || error || "Pipeline stopped"
    : complete
      ? "Pipeline complete — awaiting human approval"
      : latest?.message || "Dispatching orchestration…";

  return createPortal(
    <div className="fixed inset-0 z-[80] process-mesh backdrop-blur-xl">
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute -left-24 top-16 h-72 w-72 rounded-full border border-brass-400/20 animate-orbit" />
        <div className="absolute right-10 bottom-10 h-96 w-96 rounded-full border border-info/20 animate-orbit [animation-duration:18s]" />
      </div>
      <div className="relative h-full flex items-center justify-center p-6">
        <div className="w-full max-w-5xl border border-ink-600/80 bg-ink-950/70 shadow-[0_30px_120px_rgba(0,0,0,0.55)] animate-rise">
          <div className="relative overflow-hidden px-7 py-5 border-b border-ink-600">
            <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-brass-400 to-transparent" />
            <div className="flex items-start justify-between gap-4">
              <div>
                <div className="text-[11px] uppercase tracking-[0.28em] text-brass-400">Live orchestration</div>
                <h2 className="text-2xl font-semibold mt-1 tracking-tight">{ticketNumber || "Ticket"}</h2>
                <p className="text-sm text-mist-500 mt-1 max-w-xl">{title}</p>
              </div>
              <div className="flex items-center gap-3">
                <div className="text-right hidden sm:block">
                  <div className="text-[11px] uppercase tracking-[0.16em] text-mist-500">Executor</div>
                  <div className="mono text-xs text-mist-300 mt-0.5">{execMode || (pending ? "dispatching" : "inline")}</div>
                </div>
                <button
                  className="p-2 text-mist-500 hover:text-mist-100"
                  onClick={onClose}
                  aria-label="Close overlay"
                >
                  <X size={16} />
                </button>
              </div>
            </div>
            <div className="mt-4 flex items-center gap-4">
              <div className="flex-1 h-[3px] bg-ink-700 overflow-hidden">
                <div
                  className={`h-full transition-all duration-500 ${failed ? "bg-fail" : complete ? "bg-pass" : "bg-brass-400"}`}
                  style={{ width: `${complete ? 100 : Math.max(pending ? 6 : 0, pct)}%` }}
                />
              </div>
              <div className="mono text-sm tabular-nums text-brass-400 w-12 text-right">{complete ? 100 : pct}%</div>
            </div>
            <p className="mt-3 text-sm text-mist-100 flex items-center gap-2">
              <Cpu size={14} className={pending && !failed ? "text-brass-400 animate-pulse" : "text-mist-500"} />
              {headline}
            </p>
          </div>

          <div className="grid grid-cols-12 min-h-[420px]">
            <div className="col-span-5 border-r border-ink-600 p-5">
              <ol className="space-y-1">
                {STAGES.map((stage, i) => {
                  const Icon = stage.icon;
                  const st = states[i];
                  const isActive = i === active && pending && !failed;
                  return (
                    <li
                      key={stage.id}
                      className={`flex items-center gap-3 px-3 py-2 transition-colors ${
                        isActive ? "bg-brass-500/10 animate-pulse-glow" : ""
                      }`}
                    >
                      <span
                        className={`grid place-items-center h-8 w-8 rounded-full border ${
                          st === "done"
                            ? "border-pass/50 bg-pass/15 text-pass"
                            : st === "fail"
                              ? "border-fail/50 bg-fail/15 text-fail"
                              : isActive
                                ? "border-brass-400 text-brass-400"
                                : "border-ink-600 text-mist-500"
                        }`}
                      >
                        {st === "done" ? <Check size={14} /> : st === "fail" ? <AlertTriangle size={14} /> : <Icon size={14} />}
                      </span>
                      <div className="min-w-0 flex-1">
                        <div className={`text-sm ${isActive || st === "done" ? "text-mist-100" : "text-mist-500"}`}>
                          {stage.label}
                        </div>
                        <div className="text-[11px] text-mist-500 truncate">{stage.hint}</div>
                      </div>
                      <span className="text-[10px] uppercase tracking-[0.14em] text-mist-500">
                        {st === "done" ? "done" : st === "fail" ? "halted" : isActive ? "live" : "queued"}
                      </span>
                    </li>
                  );
                })}
              </ol>
            </div>
            <div className="col-span-7 relative p-5">
              <div className="absolute inset-x-5 top-5 bottom-5 overflow-hidden pointer-events-none">
                <div className="h-16 bg-gradient-to-b from-brass-400/10 to-transparent animate-scan" />
              </div>
              <div className="text-[11px] uppercase tracking-[0.2em] text-mist-500 mb-3">Live telemetry</div>
              <div className="relative max-h-[360px] overflow-auto space-y-2 pr-2">
                {!events.length && (
                  <div className="text-sm text-mist-500">Waiting for worker events from PostgreSQL…</div>
                )}
                {events
                  .slice()
                  .reverse()
                  .map((e, i) => (
                    <div
                      key={`${e.sequence}-${e.event_type}-${i}`}
                      className="border border-ink-600/80 bg-ink-900/60 px-3 py-2 animate-rise"
                    >
                      <div className="flex justify-between gap-3">
                        <span className="mono text-[11px] text-brass-400">{e.event_type}</span>
                        <span className="mono text-[11px] text-mist-500">{e.timestamp ? e.timestamp.slice(11, 19) : ""}</span>
                      </div>
                      <div className="text-sm mt-1 text-mist-100">{e.message}</div>
                    </div>
                  ))}
              </div>
            </div>
          </div>

          <div className="px-7 py-4 border-t border-ink-600 flex items-center justify-between gap-3">
            <div className="text-xs text-mist-500">
              Stages advance from real workflow events. Progress is not simulated.
            </div>
            {complete || failed || error ? (
              <Button onClick={onClose}>{failed || error ? "Close" : "View results"}</Button>
            ) : (
              <div className="text-xs text-brass-400 uppercase tracking-[0.16em]">Running</div>
            )}
          </div>
        </div>
      </div>
    </div>,
    document.body,
  );
}
