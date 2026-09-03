import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import Editor from "@monaco-editor/react";
import { RulesAPI } from "../api/client";
import { Badge, Card, Page } from "../components/ui";

type Node = { id: string; label: string; children: Node[]; ruleId?: string };

function buildTree(rules: any[]): Node {
  const root: Node = { id: "universal", label: "Universal", children: [] };
  const idx: Record<string, Node> = { universal: root };
  for (const r of rules) {
    const market = r.market || "Unscoped";
    const brand = r.brand || "Brand-agnostic";
    const area = r.therapeutic_area || "General";
    const mat = r.material_type || r.rule_category;
    const mk = `m:${market}`;
    const bk = `${mk}|${brand}`;
    const ak = `${bk}|${area}`;
    if (!idx[mk]) {
      idx[mk] = { id: mk, label: market, children: [] };
      root.children.push(idx[mk]);
    }
    if (!idx[bk]) {
      idx[bk] = { id: bk, label: brand, children: [] };
      idx[mk].children.push(idx[bk]);
    }
    if (!idx[ak]) {
      idx[ak] = { id: ak, label: area, children: [] };
      idx[bk].children.push(idx[ak]);
    }
    idx[ak].children.push({ id: r.id, label: `${mat} · ${r.rule_id}`, children: [], ruleId: r.rule_id });
  }
  return root;
}

function Tree({ node, depth = 0, onSelect, selected }: { node: Node; depth?: number; onSelect: (id: string) => void; selected?: string }) {
  const [open, setOpen] = useState(depth < 2);
  return (
    <div>
      <button
        className={`flex w-full text-left text-sm py-0.5 hover:text-brass-400 ${selected === node.ruleId ? "text-brass-400" : ""}`}
        style={{ paddingLeft: depth * 12 }}
        onClick={() => {
          setOpen(!open);
          if (node.ruleId) onSelect(node.ruleId);
        }}
      >
        <span className="text-mist-500 w-4">{node.children.length ? (open ? "▾" : "▸") : "·"}</span>
        {node.label}
      </button>
      {open && node.children.map((c) => <Tree key={c.id} node={c} depth={depth + 1} onSelect={onSelect} selected={selected} />)}
    </div>
  );
}

export function RuleExplorer() {
  const list = useQuery({ queryKey: ["rules"], queryFn: () => RulesAPI.list("?limit=200") });
  const [rid, setRid] = useState("RULE-US-DRUGA-CV-014");
  const detail = useQuery({ queryKey: ["rule", rid], queryFn: () => RulesAPI.get(rid), enabled: Boolean(rid) });
  const tree = useMemo(() => buildTree(list.data || []), [list.data]);
  const r = detail.data;
  return (
    <Page title="Rule Explorer" subtitle="Deterministic hierarchy: Market-Brand > Brand > Market > Universal.">
      <div className="grid grid-cols-12 gap-4">
        <Card title="Hierarchy" className="col-span-4">
          <div className="max-h-[70vh] overflow-auto">
            <Tree node={tree} onSelect={setRid} selected={rid} />
          </div>
        </Card>
        <div className="col-span-8 space-y-3">
          <Card title="Selected rule">
            <div className="flex justify-between">
              <div>
                <div className="mono text-lg">{r?.rule_id}</div>
                <div className="text-sm text-mist-500">{r?.name}</div>
              </div>
              <Badge status={r?.status}>{r?.status}</Badge>
            </div>
            <div className="grid grid-cols-3 gap-2 mt-3 text-sm">
              <div>Category {r?.rule_category}</div>
              <div>Type {r?.rule_type}</div>
              <div>Lock {r?.lock_version}</div>
            </div>
            <div className="text-xs text-mist-500 mt-2 mono">checksum {r?.current_checksum}</div>
          </Card>
          <Card title="Body">
            <div className="h-64 border border-ink-600">
              <Editor
                height="100%"
                theme="vs-dark"
                defaultLanguage="json"
                value={JSON.stringify(r?.current_body || {}, null, 2)}
                options={{ readOnly: true, minimap: { enabled: false }, fontSize: 12 }}
              />
            </div>
          </Card>
          <div className="grid grid-cols-2 gap-3">
            <Card title="Versions">
              {(r?.versions || []).map((v: any) => (
                <div key={v.id} className="flex justify-between text-sm py-1">
                  <span className="mono">
                    {v.version_label} {v.is_production ? "· Production" : ""}
                  </span>
                </div>
              ))}
            </Card>
            <Card title="Dependencies & inheritance">
              <div className="text-xs text-mist-500 mb-1">Inherited</div>
              {(r?.inherited || []).map((i: any, n: number) => (
                <div key={n} className="text-sm">
                  {i.type}
                </div>
              ))}
              <div className="text-xs text-mist-500 mt-2 mb-1">Dependencies</div>
              {(r?.dependencies || []).map((d: any, n: number) => (
                <div key={n} className="text-sm">
                  {d.type} · {d.notes}
                </div>
              ))}
            </Card>
          </div>
        </div>
      </div>
    </Page>
  );
}
