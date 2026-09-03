import { useQuery } from "@tanstack/react-query";
import { AuthAPI, PlatformAPI } from "../api/client";
import { Badge, Card, Page } from "../components/ui";

export function AdminPage() {
  const me = useQuery({ queryKey: ["me"], queryFn: AuthAPI.me });
  const ints = useQuery({ queryKey: ["ints"], queryFn: PlatformAPI.integrations });
  const citations = useQuery({ queryKey: ["cites"], queryFn: PlatformAPI.citations });
  return (
    <Page title="Administration" subtitle="RBAC, integration configuration, and scientific citation catalog.">
      <div className="grid grid-cols-2 gap-4">
        <Card title="Signed-in principal">
          <div className="text-sm">{me.data?.full_name}</div>
          <div className="text-xs text-mist-500">{me.data?.email}</div>
          <div className="mt-2 text-xs mono">{me.data?.roles?.join(", ")}</div>
        </Card>
        <Card title="Integrations">
          {(ints.data || []).map((i: any) => (
            <div key={i.name} className="flex justify-between text-sm py-1">
              <div>
                <div>{i.name}</div>
                <div className="text-[11px] text-mist-500">{i.notes}</div>
              </div>
              <Badge status={i.status === "NOT_CONFIGURED" ? "WARN" : "PASS"}>{i.status}</Badge>
            </div>
          ))}
        </Card>
        <Card title="Scientific citations (Synthetic Demo Dataset)" className="col-span-2">
          <table className="w-full text-sm">
            <thead className="text-[11px] uppercase text-mist-500">
              <tr>
                <th className="text-left py-2">ID</th>
                <th className="text-left">Year</th>
                <th className="text-left">Title</th>
                <th className="text-left">Status</th>
              </tr>
            </thead>
            <tbody>
              {(citations.data || []).map((c: any) => (
                <tr key={c.citation_id} className="border-t border-ink-600">
                  <td className="py-1 mono">{c.citation_id}</td>
                  <td>{c.year}</td>
                  <td>{c.title}</td>
                  <td>{c.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      </div>
    </Page>
  );
}
