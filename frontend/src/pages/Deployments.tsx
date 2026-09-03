import { useQuery } from "@tanstack/react-query";
import { DeployAPI } from "../api/client";
import { Badge, Card, Page } from "../components/ui";
import { fmtDate } from "../utils/format";

export function DeploymentsPage() {
  const list = useQuery({ queryKey: ["deployments"], queryFn: DeployAPI.list });
  return (
    <Page title="Deployments" subtitle="Immutable version activation. Prior versions are retained.">
      <Card>
        <table className="w-full text-sm">
          <thead className="text-[11px] uppercase text-mist-500">
            <tr>
              {["Deployment", "Ticket", "From", "To", "Smoke", "Status", "When"].map((h) => (
                <th key={h} className="text-left py-2">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {(list.data || []).map((d: any) => (
              <tr key={d.id} className="border-t border-ink-600">
                <td className="py-2 mono">{d.id.slice(0, 8)}</td>
                <td className="mono">{d.ticket_id?.slice(0, 8)}</td>
                <td className="mono">{d.from_version_id?.slice(0, 8)}</td>
                <td className="mono">{d.to_version_id?.slice(0, 8)}</td>
                <td>
                  <Badge status={d.smoke_test_status}>{d.smoke_test_status}</Badge>
                </td>
                <td>
                  <Badge status={d.status}>{d.status}</Badge>
                </td>
                <td className="text-mist-500">{fmtDate(d.deployed_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </Page>
  );
}
