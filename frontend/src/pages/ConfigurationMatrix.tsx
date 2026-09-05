import { useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ConfigAPI } from "../api/client";
import { Button, Card, Page } from "../components/ui";

export function ConfigurationMatrixPage() {
  const qc = useQueryClient();
  const fileRef = useRef<HTMLInputElement>(null);
  const [market, setMarket] = useState("");
  const [language, setLanguage] = useState("");
  const [stringType, setStringType] = useState("");
  const [brand, setBrand] = useState("");
  const params = useMemo(() => {
    const q = new URLSearchParams();
    if (market) q.set("market", market);
    if (language) q.set("language", language);
    if (stringType) q.set("string_type", stringType);
    if (brand) q.set("brand", brand);
    const s = q.toString();
    return s ? `?${s}` : "";
  }, [market, language, stringType, brand]);
  const list = useQuery({ queryKey: ["configurations", params], queryFn: () => ConfigAPI.list(params) });
  const rows = list.data?.rows || [];
  const rowCount = list.data?.count ?? rows.length;
  const languageCount = list.data?.language_count;
  const importMut = useMutation({
    mutationFn: (file: File) => ConfigAPI.importCsv(file),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["configurations"] }),
  });

  async function onExport() {
    const blob = await ConfigAPI.exportCsv();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "configuration_matrix.csv";
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <Page
      title="Configuration Matrix"
      subtitle={
        languageCount
          ? `${rowCount} Static Text rows · ${languageCount} languages. Unique matrix hit pins the config; miss or HITL Gate 1/2 falls through to the 5-tier engine.`
          : "Static Text catalog. Unique matrix hit pins the config; otherwise the 5-tier engine and HITL gate run."
      }
      actions={
        <>
          <Button variant="ghost" onClick={onExport}>
            Export CSV
          </Button>
          <Button onClick={() => fileRef.current?.click()}>Import CSV</Button>
          <input
            ref={fileRef}
            type="file"
            accept=".csv,text/csv"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) importMut.mutate(f);
              e.target.value = "";
            }}
          />
        </>
      }
    >
      <div className="text-[11px] text-mist-500 mb-3">
        {rowCount ?? "—"} rows · {languageCount ?? "—"} languages
        {importMut.data ? ` · Last import ${importMut.data.control_count}` : ""}
      </div>
      <div className="flex flex-wrap gap-2 mb-4">
        <input
          className="bg-ink-900 border border-ink-600 px-2 py-1 text-sm"
          placeholder="Market"
          value={market}
          onChange={(e) => setMarket(e.target.value)}
        />
        <input
          className="bg-ink-900 border border-ink-600 px-2 py-1 text-sm"
          placeholder="Language"
          value={language}
          onChange={(e) => setLanguage(e.target.value)}
        />
        <input
          className="bg-ink-900 border border-ink-600 px-2 py-1 text-sm"
          placeholder="String type"
          value={stringType}
          onChange={(e) => setStringType(e.target.value)}
        />
        <input
          className="bg-ink-900 border border-ink-600 px-2 py-1 text-sm"
          placeholder="Brand"
          value={brand}
          onChange={(e) => setBrand(e.target.value)}
        />
      </div>
      <Card>
        <div className="overflow-auto max-h-[70vh]">
          <table className="w-full text-sm">
            <thead className="text-[11px] uppercase text-mist-500 sticky top-0 bg-ink-900">
              <tr>
                <th className="text-left py-2 pr-3">Config</th>
                <th className="text-left pr-3">Market</th>
                <th className="text-left pr-3">Lang</th>
                <th className="text-left pr-3">Brand</th>
                <th className="text-left pr-3">TA</th>
                <th className="text-left pr-3">Type</th>
                <th className="text-left pr-3">Rule</th>
                <th className="text-left">Old value</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r: any) => (
                <tr key={r.config_id} className="border-t border-ink-600">
                  <td className="py-2 pr-3 mono text-[11px]">{r.config_id}</td>
                  <td className="pr-3">{r.market}</td>
                  <td className="pr-3">{r.language}</td>
                  <td className="pr-3">{r.brand}</td>
                  <td className="pr-3">{r.therapeutic_area}</td>
                  <td className="pr-3">{r.string_type}</td>
                  <td className="pr-3 mono text-[11px]">{r.rule_id}</td>
                  <td className="text-mist-500 max-w-xs truncate">{r.old_value}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </Page>
  );
}
