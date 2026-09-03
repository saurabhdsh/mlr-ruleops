import { useQuery } from "@tanstack/react-query";
import { PlatformAPI } from "../api/client";
import { Card, Page } from "../components/ui";
import { fmtDate } from "../utils/format";

export function AuditPage() {
  const audit = useQuery({ queryKey: ["audit"], queryFn: PlatformAPI.audit });
  return (
    <Page title="Audit & Governance" subtitle="Append-only ledger of user, system, AI, worker, and integration actors.">
      <Card>
        <table className="w-full text-sm">
          <thead className="text-[11px] uppercase text-mist-500">
            <tr>
              {["Time", "Event", "Entity", "Actor", "Checksum"].map((h) => (
                <th key={h} className="text-left py-2">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {(audit.data || []).map((a: any) => (
              <tr key={a.id} className="border-t border-ink-600">
                <td className="py-2 text-mist-500">{fmtDate(a.timestamp)}</td>
                <td className="mono">{a.event_type}</td>
                <td>
                  {a.entity_type}:{a.entity_id?.slice(0, 8)}
                </td>
                <td>
                  {a.actor_type}
                </td>
                <td className="mono text-xs">{a.checksum?.slice(0, 16) || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </Page>
  );
}
