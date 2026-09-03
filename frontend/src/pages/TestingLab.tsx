import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { PlatformAPI, RulesAPI } from "../api/client";
import { Badge, Button, Card, Page } from "../components/ui";
import { fmtPct } from "../utils/format";

const SAMPLE = {
  rule_id: "RULE-US-DRUGA-CV-014",
  market: "US",
  brand: "Drug A",
  therapeutic_area: "Cardiovascular",
  material_type: "Promotional",
  language: "EN",
  content:
    "Drug A (generic name) is indicated to reduce cardiovascular risk in appropriate adults. Supported by the 2020 outcomes study CIT-2020-001.",
};

export function TestingLab() {
  const runs = useQuery({ queryKey: ["testruns"], queryFn: PlatformAPI.testRuns });
  const [id, setId] = useState<string | null>(null);
  const detail = useQuery({ queryKey: ["testrun", id], queryFn: () => PlatformAPI.testRun(id!), enabled: Boolean(id) });
  const [content, setContent] = useState(SAMPLE.content);
  const execute = useMutation({
    mutationFn: () => RulesAPI.execute({ ...SAMPLE, content }),
  });
  return (
    <Page title="Testing Lab" subtitle="Sandbox replay of production vs proposed rule versions against historical MLR reviews.">
      <Card title="Live production engine probe">
        <p className="text-xs text-mist-500 mb-3">
          Executes the current production version of RULE-US-DRUGA-CV-014 against review context. Flags are calculated by the backend rule engine, not the UI.
        </p>
        <textarea
          className="w-full h-24 bg-ink-950 border border-ink-600 p-2 text-sm mb-3"
          value={content}
          onChange={(e) => setContent(e.target.value)}
        />
        <Button onClick={() => execute.mutate()} disabled={execute.isPending}>
          {execute.isPending ? "Executing…" : "Execute production rule"}
        </Button>
        {execute.data && (
          <div className="mt-3 text-sm">
            <div className="text-xs text-mist-500 mb-1">
              {execute.data.source} · {execute.data.rules_evaluated} rule(s)
            </div>
            <div className="mono text-xs whitespace-pre-wrap">
              {(execute.data.flags || []).join("\n") || "(no flags)"}
            </div>
            <div className="text-xs text-mist-500 mt-2">
              matched: {(execute.data.matched_rule_ids || []).join(", ") || "—"}
            </div>
          </div>
        )}
        {execute.error && <div className="mt-2 text-sm text-fail">{(execute.error as Error).message}</div>}
      </Card>
      <Card className="mt-4">
        <table className="w-full text-sm">
          <thead className="text-[11px] uppercase text-mist-500">
            <tr>
              {["Run ID", "Proposal", "Cases", "Unchanged", "Expected", "Unexpected", "FP", "FN", "Duration", "Status"].map((h) => (
                <th key={h} className="text-left py-2 pr-3">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {(runs.data || []).map((r: any) => (
              <tr key={r.id} className="border-t border-ink-600 cursor-pointer hover:bg-ink-800" onClick={() => setId(r.id)}>
                <td className="py-2 mono pr-3">{r.id.slice(0, 8)}</td>
                <td className="mono pr-3">{r.proposal_id?.slice(0, 8)}</td>
                <td>{r.total_cases}</td>
                <td>{r.unchanged_cases}</td>
                <td>{r.intentionally_changed_cases}</td>
                <td>{r.unexpected_changed_cases}</td>
                <td>{r.new_false_positives}</td>
                <td>{r.new_false_negatives}</td>
                <td>{r.duration_ms}ms</td>
                <td>
                  <Badge status={r.regression_safety}>{r.regression_safety}</Badge>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
      {id && (
        <Card title="Case-by-case" className="mt-4">
          <div className="text-xs text-mist-500 mb-2">
            Flag rate {fmtPct(detail.data?.summary?.baseline_flag_rate)} → {fmtPct(detail.data?.summary?.proposed_flag_rate)}
          </div>
          <div className="max-h-96 overflow-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-mist-500">
                  <th className="text-left py-1">Review</th>
                  <th className="text-left">Classification</th>
                  <th className="text-left">Baseline</th>
                  <th className="text-left">Proposed</th>
                  <th className="text-left">Notes</th>
                </tr>
              </thead>
              <tbody>
                {(detail.data?.results || []).map((r: any) => (
                  <tr key={r.review_id} className="border-t border-ink-600">
                    <td className="py-1 mono">{r.review_id}</td>
                    <td>{r.classification}</td>
                    <td>{(r.baseline_flags || []).join(", ")}</td>
                    <td>{(r.proposed_flags || []).join(", ")}</td>
                    <td>{r.notes}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </Page>
  );
}
