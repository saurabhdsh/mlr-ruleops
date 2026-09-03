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
    <div className="fixed inset-0 z-[80] flex items-center justify-center p-4 bg-ink-950/60 backdrop-blur-[2px]">
      <div className="w-full max-w-md max-h-[min(520px,80vh)] flex flex-col border border-ink-600 bg-ink-900 shadow-[0_16px_48px_rgba(0,0,0,0.45)]">
        <div className="shrink-0 px-4 py-3 border-b border-ink-600">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <div className="text-[10px] uppercase tracking-[0.2em] text-brass-400">Live run</div>
              <h2 className="text-base font-semibold mt-0.5 truncate">{ticketNumber || "Ticket"}</h2>
              <p className="text-[11px] text-mist-500 truncate">{title}</p>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <span className="mono text-[10px] text-mist-500">{execMode || (pending ? "…" : "inline")}</span>
              <button className="p-1 text-mist-500 hover:text-mist-100" onClick={onClose} aria-label="Close overlay">
                <X size={14} />
              </button>
            </div>
          </div>
          <div className="mt-2 flex items-center gap-2">
            <div className="flex-1 h-1 bg-ink-700 overflow-hidden">
              <div
                className={`h-full transition-all duration-500 ${failed ? "bg-fail" : complete ? "bg-pass" : "bg-brass-400"}`}
                style={{ width: `${complete ? 100 : Math.max(pending ? 6 : 0, pct)}%` }}
              />
            </div>
            <div className="mono text-[11px] tabular-nums text-brass-400 w-9 text-right">{complete ? 100 : pct}%</div>
          </div>
          <p className="mt-2 text-[12px] text-mist-100 flex items-center gap-1.5 truncate">
            <Cpu size={12} className={pending && !failed ? "text-brass-400 animate-pulse shrink-0" : "text-mist-500 shrink-0"} />
            <span className="truncate">{headline}</span>
          </p>
        </div>

        <div className="shrink-0 px-4 py-2.5 border-b border-ink-600 grid grid-cols-2 gap-1">
          {STAGES.map((stage, i) => {
            const Icon = stage.icon;
            const st = states[i];
            const isActive = i === active && pending && !failed;
            return (
              <div
                key={stage.id}
                className={`flex items-center gap-1.5 px-2 py-1 ${isActive ? "bg-brass-500/10" : ""}`}
              >
                <span
                  className={`grid place-items-center h-5 w-5 shrink-0 rounded-full border ${
                    st === "done"
                      ? "border-pass/50 bg-pass/15 text-pass"
                      : st === "fail"
                        ? "border-fail/50 bg-fail/15 text-fail"
                        : isActive
                          ? "border-brass-400 text-brass-400"
                          : "border-ink-600 text-mist-500"
                  }`}
                >
                  {st === "done" ? <Check size={10} /> : st === "fail" ? <AlertTriangle size={10} /> : <Icon size={10} />}
                </span>
                <span className={`text-[11px] truncate ${isActive || st === "done" ? "text-mist-100" : "text-mist-500"}`}>
                  {stage.label}
                </span>
              </div>
            );
          })}
        </div>

        <div className="flex-1 min-h-0 overflow-y-auto px-4 py-2 space-y-1.5">
          {!events.length && <div className="text-[12px] text-mist-500">Waiting for pipeline events…</div>}
          {events
            .slice()
            .reverse()
            .slice(0, 6)
            .map((e, i) => (
              <div key={`${e.sequence}-${e.event_type}-${i}`} className="border border-ink-600 bg-ink-950 px-2 py-1.5">
                <div className="flex justify-between gap-2">
                  <span className="mono text-[10px] text-brass-400 truncate">{e.event_type}</span>
                  <span className="mono text-[10px] text-mist-500 shrink-0">{e.timestamp ? e.timestamp.slice(11, 19) : ""}</span>
                </div>
                <div className="text-[11px] text-mist-100 truncate">{e.message}</div>
              </div>
            ))}
        </div>

        <div className="shrink-0 px-4 py-3 border-t border-ink-600 flex items-center justify-between gap-3">
          <div className="text-[11px] text-mist-500">Tata Consultancy Services</div>
          <Button onClick={onClose} disabled={pending && !failed && !error}>
            {failed || error ? "Close" : pending ? "Running…" : "View results"}
          </Button>
        </div>
      </div>
    </div>,
    document.body,
  );
}
