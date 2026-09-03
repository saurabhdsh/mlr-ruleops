import { useQuery } from "@tanstack/react-query";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { PlatformAPI } from "../api/client";
import { Card, Metric, Page } from "../components/ui";
import { fmtPct } from "../utils/format";

export function AnalyticsPage() {
  const dash = useQuery({ queryKey: ["dash"], queryFn: PlatformAPI.dashboard });
  const d = dash.data || {};
  return (
    <Page title="Analytics" subtitle="All figures are computed from persisted operational data.">
      <div className="text-[11px] text-mist-500 mb-4">Synthetic Demo Data</div>
      <div className="grid grid-cols-4 gap-3 mb-6">
        <Metric label="Avg resolution hours" value={d.average_resolution_hours ?? "—"} />
        <Metric label="Median resolution hours" value={d.median_resolution_hours ?? "—"} />
        <Metric label="Rollback rate" value={fmtPct(d.rollback_rate)} />
        <Metric label="Regression failure rate" value={fmtPct(d.regression_failure_rate)} />
      </div>
      <div className="grid grid-cols-2 gap-4">
        <Card title="Tickets by market">
          <div className="h-56">
            <ResponsiveContainer>
              <BarChart data={d.tickets_by_market || []}>
                <CartesianGrid stroke="#2a3140" vertical={false} />
                <XAxis dataKey="market" tick={{ fill: "#8b929e", fontSize: 11 }} />
                <YAxis tick={{ fill: "#8b929e", fontSize: 11 }} />
                <Tooltip contentStyle={{ background: "#181c24", border: "1px solid #2a3140" }} />
                <Bar dataKey="count" fill="#5b7c99" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>
        <Card title="Tickets by change category">
          {(d.tickets_by_change_type || []).map((x: any) => (
            <div key={x.change_type} className="flex justify-between text-sm py-1">
              <span>{x.change_type}</span>
              <span className="mono">{x.count}</span>
            </div>
          ))}
        </Card>
      </div>
    </Page>
  );
}
