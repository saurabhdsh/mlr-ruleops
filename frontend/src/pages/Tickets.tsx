import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { TicketsAPI } from "../api/client";
import { Badge, Button, Card, Page } from "../components/ui";
import { ageHours, fmtDate } from "../utils/format";

export function TicketsPage() {
  const qc = useQueryClient();
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const params = useMemo(() => {
    const p = new URLSearchParams();
    if (q) p.set("q", q);
    if (status) p.set("status", status);
    return `?${p.toString()}`;
  }, [q, status]);
  const tickets = useQuery({ queryKey: ["tickets", params], queryFn: () => TicketsAPI.list(params) });
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({
    title: "",
    description: "",
    market_hint: "US",
    brand_hint: "Drug A",
    priority: "HIGH",
  });
  const create = useMutation({
    mutationFn: () => TicketsAPI.create(form),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tickets"] });
      setOpen(false);
    },
  });

  return (
    <Page
      title="Tickets"
      subtitle="Intake from the operations console, REST API, or webhook."
      actions={<Button onClick={() => setOpen(true)}>New ticket</Button>}
    >
      <div className="flex gap-2 mb-4">
        <input
          placeholder="Search"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          className="bg-ink-900 border border-ink-600 px-3 py-1.5 text-sm w-72"
        />
        <select value={status} onChange={(e) => setStatus(e.target.value)} className="bg-ink-900 border border-ink-600 px-2 py-1.5 text-sm">
          <option value="">All stages</option>
          {["RECEIVED", "AWAITING_APPROVAL", "DEPLOYED", "CLOSED", "NEEDS_CLARIFICATION"].map((s) => (
            <option key={s}>{s}</option>
          ))}
        </select>
      </div>
      <Card>
        <table className="w-full text-sm">
          <thead className="text-[11px] uppercase text-mist-500">
            <tr>
              {["Ticket ID", "Source", "Title", "Market", "Brand", "Change type", "Risk", "Stage", "Age", "Created"].map((h) => (
                <th key={h} className="text-left py-2 pr-3 font-medium">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {(tickets.data || []).map((t: any) => (
              <tr key={t.id} className="border-t border-ink-600 hover:bg-ink-800/50">
                <td className="py-2 pr-3 mono">
                  <Link className="hover:text-brass-400" to={`/tickets/${t.id}`}>
                    {t.ticket_number}
                  </Link>
                </td>
                <td className="pr-3">{t.source_system}</td>
                <td className="pr-3 max-w-[280px] truncate">{t.title}</td>
                <td className="pr-3">{t.market_hint || "—"}</td>
                <td className="pr-3">{t.brand_hint || "—"}</td>
                <td className="pr-3">{t.change_type || "—"}</td>
                <td className="pr-3">
                  <Badge status={t.risk_level}>{t.risk_level || "—"}</Badge>
                </td>
                <td className="pr-3">
                  <Badge status={t.status}>{t.status}</Badge>
                </td>
                <td className="pr-3">{ageHours(t.created_at)}</td>
                <td className="text-mist-500">{fmtDate(t.created_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
      {open && (
        <div className="fixed inset-0 bg-black/50 grid place-items-center z-50">
          <form
            className="w-[560px] bg-ink-900 border border-ink-600 p-6"
            onSubmit={(e) => {
              e.preventDefault();
              create.mutate();
            }}
          >
            <h2 className="text-lg mb-4">Create ticket</h2>
            <input
              className="w-full bg-ink-950 border border-ink-600 px-3 py-2 text-sm mb-3"
              placeholder="Title"
              value={form.title}
              onChange={(e) => setForm({ ...form, title: e.target.value })}
            />
            <textarea
              className="w-full bg-ink-950 border border-ink-600 px-3 py-2 text-sm mb-3 h-28"
              placeholder="Description"
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
            />
            <div className="grid grid-cols-2 gap-2 mb-4">
              <input
                className="bg-ink-950 border border-ink-600 px-3 py-2 text-sm"
                value={form.market_hint}
                onChange={(e) => setForm({ ...form, market_hint: e.target.value })}
              />
              <input
                className="bg-ink-950 border border-ink-600 px-3 py-2 text-sm"
                value={form.brand_hint}
                onChange={(e) => setForm({ ...form, brand_hint: e.target.value })}
              />
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="ghost" onClick={() => setOpen(false)}>
                Cancel
              </Button>
              <Button type="submit">Create</Button>
            </div>
          </form>
        </div>
      )}
    </Page>
  );
}
