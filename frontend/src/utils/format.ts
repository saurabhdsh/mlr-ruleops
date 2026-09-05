export function fmtPct(n: number | undefined) {
  if (n == null) return "—";
  return `${(n * 100).toFixed(2)}%`;
}

export function fmtDate(value?: string | null) {
  if (!value) return "—";
  return new Date(value).toLocaleString();
}

export function ageHours(created?: string) {
  if (!created) return "—";
  const h = (Date.now() - new Date(created).getTime()) / 3600000;
  if (h < 1) return `${Math.round(h * 60)}m`;
  if (h < 48) return `${h.toFixed(1)}h`;
  return `${(h / 24).toFixed(1)}d`;
}

export function statusTone(status?: string) {
  const s = (status || "").toUpperCase();
  if (["PASS", "DEPLOYED", "APPROVED", "CLOSED", "SUCCESS", "ACTIVE"].includes(s)) return "text-pass";
  if (["WARN", "AWAITING_APPROVAL", "HIGH", "NEEDS_CLARIFICATION"].includes(s)) return "text-warn";
  if (["FAIL", "FAILED", "REJECTED", "CRITICAL", "VALIDATION_FAILED"].includes(s)) return "text-fail";
  return "text-info";
}

export function pill(status?: string) {
  const s = (status || "").toUpperCase();
  if (["PASS", "DEPLOYED", "APPROVED", "CLOSED", "SUCCESS"].includes(s)) return "bg-pass/15 text-pass";
  if (["WARN", "AWAITING_APPROVAL", "HIGH", "PENDING", "GATE2-RULEMATCH", "GATE1-INTENTCONFIRM"].includes(s))
    return "bg-warn/15 text-warn";
  if (["FAIL", "FAILED", "REJECTED", "CRITICAL", "GATE3-BLOCK/RMCB"].includes(s)) return "bg-fail/15 text-fail";
  return "bg-info/15 text-info";
}
