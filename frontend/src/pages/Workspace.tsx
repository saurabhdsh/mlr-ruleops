import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate, useParams } from "react-router-dom";
import { ApprovalsAPI, DeployAPI, ProposalsAPI, TicketsAPI, sseUrl } from "../api/client";
import { ProcessRunOverlay, type RunEvent } from "../components/ProcessRunOverlay";
import { Badge, Button, Card, Page } from "../components/ui";
import { fmtDate, fmtPct } from "../utils/format";

const TABS = [
  "Interpretation",
  "Rule Resolution",
  "Proposed Change",
  "Validation",
  "Testing",
  "Impact",
  "Risk",
  "Approval",
  "Deployment",
  "Audit",
];

export function WorkspacePage() {
  const { id } = useParams();
  const nav = useNavigate();
  const qc = useQueryClient();
  const tickets = useQuery({ queryKey: ["tickets"], queryFn: () => TicketsAPI.list("?limit=50") });
  const selectedId = id || tickets.data?.find((t: any) => t.ticket_number === "TKT-1001")?.id || tickets.data?.[0]?.id;
  const ws = useQuery({
    queryKey: ["workspace", selectedId],
    queryFn: () => TicketsAPI.get(selectedId),
    enabled: Boolean(selectedId),
    refetchInterval: 2500,
  });
  const process = useMutation({
    mutationFn: () => TicketsAPI.process(selectedId),
    onSuccess: (data) => {
      setExecMode(data.execution?.mode || null);
      qc.setQueryData(["workspace", selectedId], data);
      qc.invalidateQueries({ queryKey: ["tickets"] });
      const fresh = (data.workflow_events || []).filter((e: RunEvent) => {
        if (!e.timestamp) return true;
        return Date.parse(e.timestamp) >= runStartedAt.current - 2000;
      });
      if (fresh.length) setRunEvents(fresh);
    },
  });
  const [tab, setTab] = useState("Interpretation");
  const [comment, setComment] = useState("Approved — citation swap is scientifically justified for the intended US Drug A cardiovascular promotional scope.");
  const [events, setEvents] = useState<any[]>([]);
  const [execMode, setExecMode] = useState<string | null>(null);
  const [runOpen, setRunOpen] = useState(false);
  const [runEvents, setRunEvents] = useState<RunEvent[]>([]);
  const runOpenRef = useRef(false);
  const runStartedAt = useRef(0);

  useEffect(() => {
    runOpenRef.current = runOpen;
  }, [runOpen]);

  useEffect(() => {
    if (!selectedId) return;
    const es = new EventSource(sseUrl(selectedId));
    es.addEventListener("workflow", (ev) => {
      const data = JSON.parse((ev as MessageEvent).data);
      setEvents((prev) => [...prev.filter((p) => p.sequence !== data.sequence), data].sort((a, b) => a.sequence - b.sequence));
      if (!runOpenRef.current) return;
      const ts = data.timestamp ? Date.parse(data.timestamp) : Date.now();
      if (ts + 2000 < runStartedAt.current) return;
      setRunEvents((prev) =>
        [...prev.filter((p) => p.sequence !== data.sequence || p.event_type !== data.event_type), data].sort(
          (a, b) => (a.sequence || 0) - (b.sequence || 0),
        ),
      );
    });
    return () => es.close();
  }, [selectedId]);

  function startProcess() {
    setRunEvents([]);
    runStartedAt.current = Date.now();
    setRunOpen(true);
    process.mutate();
  }

  const data = ws.data;
  const t = data?.ticket;
  const intent = data?.interpretation?.structured_output;
  const diff = data?.proposal?.semantic_diff;
  const live = events.length ? events : data?.workflow_events || [];

  const approve = useMutation({
    mutationFn: (deploy: boolean) => ApprovalsAPI.approve(data.approval.id, comment, deploy),
    onSuccess: (res) => qc.setQueryData(["workspace", selectedId], res),
  });
  const reject = useMutation({
    mutationFn: () => ApprovalsAPI.reject(data.approval.id, comment || "Rejected"),
    onSuccess: (res) => qc.setQueryData(["workspace", selectedId], res),
  });
  const changes = useMutation({
    mutationFn: () => ApprovalsAPI.requestChange(data.approval.id, comment || "Please revise"),
    onSuccess: (res) => qc.setQueryData(["workspace", selectedId], res),
  });

  const rollbackTarget = data?.proposal?.versions?.find((v: any) => !v.is_production);
  const deployments = useQuery({ queryKey: ["deps"], queryFn: DeployAPI.list });
  const rollback = useMutation({
    mutationFn: async () => {
      const dep = (deployments.data || []).find((d: any) => d.ticket_id === t.id) || (deployments.data || [])[0];
      const target = data.proposal.versions.find((v: any) => v.id === data.proposal.base_rule_version_id);
      return DeployAPI.rollback(dep.id, {
        target_version_id: target.id,
        reason: "Controlled rollback from Change Workspace",
        ticket_id: t.id,
        rule_id: data.proposal.target_rule_pk,
      });
    },
    onSuccess: () => ws.refetch(),
  });
  const revalidate = useMutation({
    mutationFn: () => ProposalsAPI.validate(data.proposal.id),
    onSuccess: (res) => qc.setQueryData(["workspace", selectedId], res),
  });
  const retest = useMutation({
    mutationFn: () => ProposalsAPI.test(data.proposal.id),
    onSuccess: (res) => {
      qc.setQueryData(["workspace", selectedId], res);
      qc.invalidateQueries({ queryKey: ["testruns"] });
    },
  });

  if (!selectedId) {
    return (
      <Page title="Change Intelligence Workspace">
        <div className="text-mist-500">No tickets available.</div>
      </Page>
    );
  }

  return (
    <Page
      title="Change Intelligence Workspace"
      subtitle={t ? `${t.ticket_number} · ${t.title}` : "Select a ticket"}
      actions={
        <>
          <select
            className="bg-ink-900 border border-ink-600 text-sm px-2 py-1.5"
            value={selectedId}
            onChange={(e) => nav(`/tickets/${e.target.value}`)}
          >
            {(tickets.data || []).map((x: any) => (
              <option key={x.id} value={x.id}>
                {x.ticket_number}
              </option>
            ))}
          </select>
          <Button onClick={startProcess} disabled={process.isPending}>
            {process.isPending ? "Processing…" : "Process ticket"}
          </Button>
          {execMode && (
            <span className="text-[11px] text-mist-500">{execMode}</span>
          )}
        </>
      }
    >
      {data?.interpretation?.is_local_fallback && (
        <div className="mb-4 text-sm border border-brass-500/40 bg-brass-500/10 px-3 py-2">
          Local deterministic interpretation mode · provider {data.interpretation.provider_name} · {data.interpretation.model_name}
        </div>
      )}
      {process.error && (
        <div className="mb-4 text-sm border border-fail/40 text-fail px-3 py-2">
          {(process.error as Error).message}
        </div>
      )}

      <ProcessRunOverlay
        open={runOpen}
        ticketNumber={t?.ticket_number}
        title={t?.title}
        events={runEvents}
        pending={process.isPending}
        error={process.error ? (process.error as Error).message : null}
        execMode={execMode}
        onClose={() => {
          setRunOpen(false);
          if (process.isSuccess) setTab("Interpretation");
        }}
      />

      <div className="grid grid-cols-4 gap-3 mb-4">
        <Card title="Original request">
          <div className="text-xs text-mist-500 mb-1">{t?.requester_name} · {t?.source_system}</div>
          <div className="text-sm leading-relaxed">{t?.description}</div>
        </Card>
        <Card title="AI interpretation">
          <div className="text-sm">{intent?.intent || "—"}</div>
          <div className="text-xs text-mist-500 mt-1">{intent?.change_type}</div>
          <div className="mt-2 text-sm">Confidence {intent ? Math.round((data.interpretation.overall_confidence || 0) * 100) : "—"}%</div>
        </Card>
        <Card title="Target rule & hierarchy">
          <div className="mono text-sm">{data?.proposal?.target_rule_id || "—"}</div>
          <div className="text-xs text-mist-500 mt-2 leading-relaxed">{data?.proposal?.decision_record}</div>
        </Card>
        <Card title="Proposed change">
          <div className="text-xs space-y-1">
            {(data?.proposal?.operations || []).map((o: any, i: number) => (
              <div key={i} className="mono">
                {o.operation} {String(o.value).slice(0, 48)}
              </div>
            ))}
            {!data?.proposal && <div className="text-mist-500">Process the ticket to generate a proposal.</div>}
          </div>
        </Card>
      </div>

      <div className="grid grid-cols-12 gap-4">
        <div className="col-span-3 space-y-3">
          <Card title="Requester">
            <div className="text-sm">{t?.requester_name}</div>
            <div className="text-xs text-mist-500">{t?.requester_email}</div>
            <div className="text-xs mt-2">Priority {t?.priority}</div>
            <div className="text-xs">Due {fmtDate(t?.due_date)}</div>
          </Card>
          <Card title="Attachments">
            {(data?.attachments || []).length === 0 && <div className="text-sm text-mist-500">None</div>}
            {(data?.attachments || []).map((a: any) => (
              <div key={a.id} className="text-sm">
                {a.filename}
              </div>
            ))}
          </Card>
          <Card title="Ticket history">
            <div className="max-h-64 overflow-auto space-y-2 text-xs">
              {(data?.comments || []).map((c: any) => (
                <div key={c.id}>
                  <div className="text-mist-500">{c.author_type}</div>
                  {c.body}
                </div>
              ))}
              {(data?.audit || []).slice(-6).map((a: any) => (
                <div key={a.id} className="text-mist-500">
                  {a.event_type}
                </div>
              ))}
            </div>
          </Card>
        </div>
        <div className="col-span-6">
          <Card title="Workflow progression">
            <ol className="space-y-2 max-h-[520px] overflow-auto">
              {live.map((e: any) => (
                <li key={e.id || e.sequence} className="flex gap-3 text-sm">
                  <span className="mono text-mist-500 w-6">{e.sequence}</span>
                  <div>
                    <div>{e.message}</div>
                    <div className="text-[11px] text-mist-500">{fmtDate(e.timestamp)}</div>
                  </div>
                </li>
              ))}
              {!live.length && <div className="text-mist-500 text-sm">No workflow events yet. Process the ticket.</div>}
            </ol>
          </Card>
        </div>
        <div className="col-span-3 space-y-3">
          <Card title="Confidence">
            <div className="text-3xl">{intent ? `${Math.round((data.interpretation.overall_confidence || 0) * 100)}%` : "—"}</div>
            <div className="text-xs text-mist-500 mt-1">{data?.llm_mode}</div>
          </Card>
          <Card title="Risk indicators">
            {(intent?.risk_indicators || []).map((r: string) => (
              <div key={r} className="text-sm">
                {r}
              </div>
            ))}
            <div className="mt-2">
              <Badge status={t?.risk_level}>{t?.risk_level || data?.risk?.overall || "UNSCORED"}</Badge>
            </div>
          </Card>
          <Card title="Current stage">
            <Badge status={t?.status}>{t?.status}</Badge>
          </Card>
        </div>
      </div>

      <div className="mt-5 border-b border-ink-600 flex gap-1 overflow-auto">
        {TABS.map((name) => (
          <button
            key={name}
            onClick={() => setTab(name)}
            className={`px-3 py-2 text-sm whitespace-nowrap ${tab === name ? "border-b-2 border-brass-400 text-mist-100" : "text-mist-500"}`}
          >
            {name}
          </button>
        ))}
      </div>
      <div className="mt-4">
        {tab === "Interpretation" && <InterpretationPane data={data} />}
        {tab === "Rule Resolution" && <ResolutionPane data={data} />}
        {tab === "Proposed Change" && <DiffPane diff={diff} proposal={data?.proposal} />}
        {tab === "Validation" && (
          <ValidationPane data={data} onRerun={() => revalidate.mutate()} pending={revalidate.isPending} />
        )}
        {tab === "Testing" && (
          <TestingPane data={data} onRerun={() => retest.mutate()} pending={retest.isPending} />
        )}
        {tab === "Impact" && <ImpactPane data={data} />}
        {tab === "Risk" && <RiskPane data={data} />}
        {tab === "Approval" && (
          <div className="grid grid-cols-2 gap-4">
            <Card title="Approval policy">
              <div className="text-sm">Required roles</div>
              <div className="mono text-xs mt-1">{(data?.approval?.required_roles || []).join(" + ") || "—"}</div>
              <div className="mt-3 text-sm">Status {data?.approval?.status || "—"}</div>
              {(data?.approval?.decisions || []).map((d: any) => (
                <div key={d.id} className="text-xs mt-2 border-t border-ink-600 pt-2">
                  {d.approver_role} · {d.decision} · {fmtDate(d.timestamp)}
                  <div className="text-mist-500">{d.comment}</div>
                </div>
              ))}
            </Card>
            <Card title="Decision">
              <textarea className="w-full h-24 bg-ink-950 border border-ink-600 p-2 text-sm" value={comment} onChange={(e) => setComment(e.target.value)} />
              <div className="flex flex-wrap gap-2 mt-3">
                <Button onClick={() => approve.mutate(false)} disabled={!data?.approval}>
                  Approve
                </Button>
                <Button onClick={() => approve.mutate(true)} disabled={!data?.approval}>
                  Approve & Deploy
                </Button>
                <Button variant="ghost" onClick={() => changes.mutate()} disabled={!data?.approval}>
                  Request changes
                </Button>
                <Button variant="danger" onClick={() => reject.mutate()} disabled={!data?.approval}>
                  Reject
                </Button>
              </div>
            </Card>
          </div>
        )}
        {tab === "Deployment" && (
          <Card title="Production versions">
            <div className="space-y-2 text-sm">
              {(data?.proposal?.versions || []).map((v: any) => (
                <div key={v.id} className="flex justify-between">
                  <span className="mono">
                    {v.version_label} {v.is_production ? "· Production" : ""}
                  </span>
                  <span className="text-mist-500 mono">{v.checksum_sha256?.slice(0, 16)}</span>
                </div>
              ))}
            </div>
            <div className="mt-4">
              <Button variant="ghost" onClick={() => rollback.mutate()} disabled={!rollbackTarget}>
                Rollback to base version
              </Button>
            </div>
          </Card>
        )}
        {tab === "Audit" && (
          <Card title="Immutable audit timeline">
            <ol className="space-y-2">
              {(data?.audit || []).map((a: any) => (
                <li key={a.id} className="text-sm flex gap-3">
                  <span className="text-mist-500 w-48 shrink-0">{fmtDate(a.timestamp)}</span>
                  <span className="mono">{a.event_type}</span>
                  <span className="text-mist-500">{a.actor_type}</span>
                  {a.checksum && <span className="mono text-[11px] text-mist-500">{a.checksum.slice(0, 12)}</span>}
                </li>
              ))}
            </ol>
          </Card>
        )}
      </div>
    </Page>
  );
}

function InterpretationPane({ data }: { data: any }) {
  const s = data?.interpretation?.structured_output;
  const ents = data?.interpretation?.entities || [];
  return (
    <div className="grid grid-cols-2 gap-4">
      <Card title="Structured intent">
        <pre className="text-xs whitespace-pre-wrap mono">{JSON.stringify(s, null, 2)}</pre>
      </Card>
      <div className="space-y-3">
        <Card title="Entities">
          {ents.map((e: any) => (
            <div key={e.field_name} className="flex justify-between text-sm py-1">
              <span>{e.field_name}</span>
              <span>
                {e.value} · {Math.round((e.confidence || 0) * 100)}%
              </span>
            </div>
          ))}
        </Card>
        <Card title="Sources used by AI">
          {(data?.interpretation?.sources_used || []).map((s: any) => (
            <div key={s.source_identifier} className="text-sm mb-2">
              <div className="mono">{s.source_identifier}</div>
              <div className="text-xs text-mist-500">
                {s.source_type} · {s.why_relevant} · score {s.retrieval_score}
              </div>
              <div className="text-xs mt-1">{s.snippet}</div>
            </div>
          ))}
        </Card>
        <Card title="Model metadata">
          <div className="text-xs space-y-1">
            <div>Provider {data?.interpretation?.provider_name}</div>
            <div>Model {data?.interpretation?.model_name}</div>
            <div>Prompt {data?.interpretation?.prompt_template_version}</div>
            <div>Schema {data?.interpretation?.output_schema_version}</div>
            <div>Completed {fmtDate(data?.interpretation?.completed_at)}</div>
          </div>
        </Card>
      </div>
    </div>
  );
}

function ResolutionPane({ data }: { data: any }) {
  return (
    <Card title="Why this rule?">
      <p className="text-sm leading-relaxed max-w-3xl">{data?.proposal?.decision_record || "Process the ticket to resolve the hierarchy."}</p>
      <div className="mt-4 text-sm">Selected {data?.proposal?.target_rule_id || "—"}</div>
    </Card>
  );
}

function DiffPane({ diff, proposal }: { diff: any; proposal: any }) {
  const logic = proposal?.proposed_body?.rule_type === "LOGIC";
  return (
    <div className="grid grid-cols-2 gap-4">
      <Card title="Current">
        <pre className="text-xs whitespace-pre-wrap leading-relaxed">
          {diff?.removed_text || JSON.stringify(diff?.current || proposal?.current_body, null, 2)}
        </pre>
        <div className="mt-3 text-xs text-mist-500">References: {(diff?.current?.references || proposal?.current_body?.references || []).map((r: any) => r.id).join(", ")}</div>
      </Card>
      <Card title="Proposed">
        <pre className="text-xs whitespace-pre-wrap leading-relaxed">
          {diff?.added_text || JSON.stringify(diff?.proposed || proposal?.proposed_body, null, 2)}
        </pre>
        <div className="mt-3 text-xs">
          <span className="diff-del px-1 mr-2">{(diff?.removed_references || []).join(", ")}</span>
          <span className="diff-add px-1">{(diff?.added_references || []).join(", ")}</span>
        </div>
      </Card>
      {logic && (
        <Card title="Condition builder" className="col-span-2">
          <LogicVisual body={proposal.proposed_body} />
        </Card>
      )}
    </div>
  );
}

function LogicVisual({ body }: { body: any }) {
  const conds = body?.when?.all || body?.when?.any || [];
  return (
    <div className="text-sm">
      <div className="text-mist-500 mb-2">IF</div>
      {conds.map((c: any, i: number) => (
        <div key={i} className="mono">
          {i > 0 ? "AND " : ""}
          {c.field} {c.operator} {c.value}
        </div>
      ))}
      <div className="text-mist-500 mt-3 mb-2">THEN</div>
      {(body.actions || []).map((a: any, i: number) => (
        <div key={i} className="mono">
          {a.type} → {a.target || a.value}
        </div>
      ))}
    </div>
  );
}

function ValidationPane({ data, onRerun, pending }: { data: any; onRerun: () => void; pending: boolean }) {
  return (
    <Card title="Validator results">
      <div className="mb-3">
        <Button onClick={onRerun} disabled={!data?.proposal || pending}>
          {pending ? "Re-running…" : "Re-run validation"}
        </Button>
      </div>
      <table className="w-full text-sm">
        <thead className="text-[11px] uppercase text-mist-500">
          <tr>
            <th className="text-left py-2">Validator</th>
            <th className="text-left">Status</th>
            <th className="text-left">Message</th>
          </tr>
        </thead>
        <tbody>
          {(data?.validation?.results || []).map((r: any) => (
            <tr key={r.validator_name} className="border-t border-ink-600">
              <td className="py-2">{r.validator_name}</td>
              <td>
                <Badge status={r.status}>{r.status}</Badge>
              </td>
              <td className="text-mist-300">{r.message}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  );
}

function TestingPane({ data, onRerun, pending }: { data: any; onRerun: () => void; pending: boolean }) {
  const tr = data?.test_run;
  return (
    <div>
      <div className="mb-3">
        <Button onClick={onRerun} disabled={!data?.proposal || pending}>
          {pending ? "Re-running…" : "Re-run sandbox + regression"}
        </Button>
      </div>
      <div className="grid grid-cols-4 gap-3 mb-4">
        <Card>
          <div className="text-xs text-mist-500">Historical reviews replayed</div>
          <div className="text-2xl">{tr?.total_cases ?? "—"}</div>
        </Card>
        <Card>
          <div className="text-xs text-mist-500">Unchanged / intended / unexpected</div>
          <div className="text-lg">
            {tr?.unchanged_cases ?? "—"} / {tr?.intentionally_changed_cases ?? "—"} / {tr?.unexpected_changed_cases ?? "—"}
          </div>
        </Card>
        <Card>
          <div className="text-xs text-mist-500">Baseline → proposed flag rate</div>
          <div className="text-lg">
            {fmtPct(tr?.baseline_flag_rate)} → {fmtPct(tr?.proposed_flag_rate)}
          </div>
          <div className="text-xs text-mist-500">Δ {fmtPct(tr?.flag_rate_delta)}</div>
        </Card>
        <Card>
          <div className="text-xs text-mist-500">Regression safety</div>
          <div className="mt-1">
            <Badge status={tr?.regression_safety}>{tr?.regression_safety || "—"}</Badge>
          </div>
          <div className="text-xs mt-2">
            FP {tr?.new_false_positives ?? "—"} · FN {tr?.new_false_negatives ?? "—"}
          </div>
        </Card>
      </div>
      <Card title="Case results">
        <div className="max-h-80 overflow-auto">
          <table className="w-full text-xs">
            <thead className="text-mist-500">
              <tr>
                <th className="text-left py-1">Review</th>
                <th className="text-left">Class</th>
                <th className="text-left">Baseline flags</th>
                <th className="text-left">Proposed flags</th>
              </tr>
            </thead>
            <tbody>
              {(tr?.results || []).map((r: any) => (
                <tr key={r.review_id} className="border-t border-ink-600">
                  <td className="py-1 mono">{r.review_id}</td>
                  <td>{r.classification}</td>
                  <td>{(r.baseline_flags || []).join(", ")}</td>
                  <td>{(r.proposed_flags || []).join(", ")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}

function ImpactPane({ data }: { data: any }) {
  const i = data?.impact || {};
  return (
    <div className="grid grid-cols-4 gap-3">
      <Card title="Change blast radius">
        <div className="space-y-1 text-sm">
          <div>{i.modified_rules ?? "—"} rule modified</div>
          <div>{(i.markets_affected || []).length} market(s) affected</div>
          <div>{(i.brands_affected || []).length} brand(s) affected</div>
          <div>{i.historical_records_affected ?? "—"} historical reviews impacted</div>
          <div>{i.dependent_rules_inspected ?? "—"} dependent rules inspected</div>
          <div>{i.unrelated_markets_impacted ?? 0} other markets impacted</div>
          <div>{i.unrelated_brands_impacted ?? 0} other brands impacted</div>
        </div>
      </Card>
      <Card title="Markets">{(i.markets_affected || []).join(", ") || "—"}</Card>
      <Card title="Brands">{(i.brands_affected || []).join(", ") || "—"}</Card>
      <Card title="Materials">{(i.material_types_affected || []).join(", ") || "—"}</Card>
    </div>
  );
}

function RiskPane({ data }: { data: any }) {
  const dims = data?.risk?.dimensions || {};
  return (
    <div className="grid grid-cols-2 gap-4">
      <Card title="Risk matrix">
        <div className="mb-3">
          Overall <Badge status={data?.risk?.overall}>{data?.risk?.overall || "—"}</Badge>
        </div>
        {Object.entries(dims).map(([k, v]) => (
          <div key={k} className="flex justify-between text-sm py-1 border-t border-ink-600">
            <span>{k.replaceAll("_", " ")}</span>
            <Badge status={String(v)}>{String(v)}</Badge>
          </div>
        ))}
      </Card>
      <Card title="Rationale">
        <p className="text-sm leading-relaxed">{data?.risk?.rationale}</p>
        <p className="text-xs text-mist-500 mt-3">{data?.risk?.ai_summary}</p>
        <p className="text-xs mt-2">Policy gate: {data?.risk?.policy_gate}</p>
      </Card>
    </div>
  );
}
