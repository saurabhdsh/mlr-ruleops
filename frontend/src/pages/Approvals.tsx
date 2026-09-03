import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { ApprovalsAPI } from "../api/client";
import { Badge, Button, Card, Page } from "../components/ui";

export function ApprovalsPage() {
  const qc = useQueryClient();
  const list = useQuery({ queryKey: ["approvals"], queryFn: ApprovalsAPI.list });
  const [comment, setComment] = useState("Approved by MLR administration.");
  const approve = useMutation({
    mutationFn: (id: string) => ApprovalsAPI.approve(id, comment, true),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["approvals"] }),
  });
  return (
    <Page title="Approvals" subtitle="Human-in-the-loop gate. LLM output cannot approve deployment.">
      <Card>
        <table className="w-full text-sm">
          <thead className="text-[11px] uppercase text-mist-500">
            <tr>
              {["Ticket", "Title", "Risk", "Roles", "Status", "Action"].map((h) => (
                <th key={h} className="text-left py-2">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {(list.data || []).map((a: any) => (
              <tr key={a.id} className="border-t border-ink-600">
                <td className="py-2 mono">
                  <Link to={`/tickets/${a.ticket_id}`} className="hover:text-brass-400">
                    {a.ticket_number}
                  </Link>
                </td>
                <td>{a.title}</td>
                <td>
                  <Badge status={a.risk_level_at_request}>{a.risk_level_at_request}</Badge>
                </td>
                <td className="text-xs">{a.required_roles}</td>
                <td>
                  <Badge status={a.status}>{a.status}</Badge>
                </td>
                <td>
                  {a.status === "PENDING" && (
                    <Button onClick={() => approve.mutate(a.id)}>Approve & deploy</Button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <textarea className="mt-4 w-full bg-ink-950 border border-ink-600 p-2 text-sm" value={comment} onChange={(e) => setComment(e.target.value)} />
      </Card>
    </Page>
  );
}
