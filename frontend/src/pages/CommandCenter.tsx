import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { PlatformAPI, TicketsAPI } from "../api/client";
import { Badge, Card, Metric, Page } from "../components/ui";
import { fmtPct } from "../utils/format";

export function CommandCenter() {
  const dash = useQuery({ queryKey: ["dash"], queryFn: PlatformAPI.dashboard });
  const tickets = useQuery({ queryKey: ["tickets"], queryFn: () => TicketsAPI.list("?limit=8") });
  const ints = useQuery({ queryKey: ["ints"], queryFn: PlatformAPI.integrations });
  const d = dash.data || {};
  return (
    <Page title="Command Center" subtitle="Operational posture across rule change intake, validation, and deployment.">
      <div className="text-[11px] text-mist-500 mb-4">Tata Consultancy Services</div>
      <div className="grid grid-cols-4 gap-3 mb-6">
        <Metric label="Open tickets" value={d.open_tickets ?? "—"} />
        <Metric label="Processing" value={d.processing ?? "—"} />
        <Metric label="Awaiting approval" value={d.awaiting_approval ?? "—"} />
        <Metric label="High risk" value={d.high_risk ?? "—"} />
        <Metric label="Avg resolution (h)" value={d.average_resolution_hours ?? "—"} />
        <Metric label="Rules in production" value={d.rules_in_production ?? "—"} />
        <Metric label="Active configurations" value={d.active_configurations ?? "—"} />
        <Metric label="Deployments today" value={d.deployments_today ?? "—"} />
        <Metric label="Regression pass rate" value={fmtPct(d.regression_pass_rate)} />
      </div>
      <div className="grid grid-cols-3 gap-4">
        <Card title="Workflow stage distribution" className="col-span-2">
          <div className="h-56">
            <ResponsiveContainer>
              <BarChart data={d.stage_distribution || []}>
                <CartesianGrid stroke="#2a3140" vertical={false} />
                <XAxis dataKey="status" tick={{ fill: "#8b929e", fontSize: 10 }} interval={0} angle={-25} textAnchor="end" height={70} />
                <YAxis tick={{ fill: "#8b929e", fontSize: 11 }} />
                <Tooltip contentStyle={{ background: "#181c24", border: "1px solid #2a3140" }} />
                <Bar dataKey="count" fill="#c4a574" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>
        <Card title="Risk distribution">
          <div className="space-y-2">
            {(d.risk_distribution || []).map((r: any) => (
              <div key={r.risk} className="flex justify-between text-sm">
                <span>{r.risk}</span>
                <span className="mono">{r.count}</span>
              </div>
            ))}
          </div>
        </Card>
        <Card title="Pending approvals">
          <div className="space-y-2 text-sm">
            {(d.pending_approvals || []).map((t: any) => (
              <Link key={t.id} to={`/tickets/${t.id}`} className="flex justify-between hover:text-brass-400">
                <span className="mono">{t.ticket_number}</span>
                <Badge status={t.risk_level}>{t.risk_level || "—"}</Badge>
              </Link>
            ))}
            {!d.pending_approvals?.length && <div className="text-mist-500">No pending approvals.</div>}
          </div>
        </Card>
        <Card title="Recent deployments">
          {(d.recent_deployments || []).map((x: any) => (
            <div key={x.id} className="flex justify-between text-sm py-1">
              <span className="mono">{x.id.slice(0, 8)}</span>
              <Badge status={x.status}>{x.status}</Badge>
            </div>
          ))}
          {!d.recent_deployments?.length && <div className="text-mist-500 text-sm">No deployments yet.</div>}
        </Card>
        <Card title="Integration health">
          {(ints.data || []).map((i: any) => (
            <div key={i.name} className="flex justify-between text-sm py-1 gap-2">
              <span>{i.name}</span>
              <Badge status={i.status === "NOT_CONFIGURED" ? "WARN" : "PASS"}>{i.status}</Badge>
            </div>
          ))}
        </Card>
      </div>
      <Card title="Recent tickets" className="mt-4">
        <table className="w-full text-sm">
          <thead className="text-mist-500 text-[11px] uppercase">
            <tr>
              <th className="text-left py-2">ID</th>
              <th className="text-left">Title</th>
              <th className="text-left">Stage</th>
              <th className="text-left">Risk</th>
            </tr>
          </thead>
          <tbody>
            {(tickets.data || []).map((t: any) => (
              <tr key={t.id} className="border-t border-ink-600">
                <td className="py-2 mono">
                  <Link to={`/tickets/${t.id}`} className="hover:text-brass-400">
                    {t.ticket_number}
                  </Link>
                </td>
                <td>{t.title}</td>
                <td>
                  <Badge status={t.status}>{t.status}</Badge>
                </td>
                <td>{t.risk_level || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </Page>
  );
}
