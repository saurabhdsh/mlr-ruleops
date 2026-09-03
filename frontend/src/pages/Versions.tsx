import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { RulesAPI } from "../api/client";
import { Badge, Card, Page } from "../components/ui";

export function VersionsPage() {
  const rules = useQuery({ queryKey: ["rules"], queryFn: () => RulesAPI.list("?limit=200") });
  const [rid, setRid] = useState("RULE-US-DRUGA-CV-014");
  const versions = useQuery({ queryKey: ["versions", rid], queryFn: () => RulesAPI.versions(rid), enabled: Boolean(rid) });
  return (
    <Page title="Rule Versions" subtitle="Every production pointer change creates a new immutable version with SHA-256 checksum.">
      <div className="flex gap-2 mb-4">
        <select className="bg-ink-900 border border-ink-600 px-2 py-1.5 text-sm" value={rid} onChange={(e) => setRid(e.target.value)}>
          {(rules.data || []).map((r: any) => (
            <option key={r.rule_id} value={r.rule_id}>
              {r.rule_id}
            </option>
          ))}
        </select>
      </div>
      <Card>
        {(versions.data || []).map((v: any) => (
          <div key={v.id} className="border-b border-ink-600 py-3">
            <div className="flex justify-between">
              <div className="mono">
                {v.version_label} {v.is_production ? "· Production" : ""}
              </div>
              <Badge status={v.is_production ? "PASS" : "INFO"}>{v.checksum_sha256?.slice(0, 16)}</Badge>
            </div>
            <div className="text-xs text-mist-500 mt-1">{v.change_summary}</div>
          </div>
        ))}
      </Card>
    </Page>
  );
}
