// 管理画面の「実績の書き出し」: 期間(完了日の稼働日)とラインで、片付けが終わった計画の一覧を出す。
// 生産数は行ごとに直せる。キッティングNo.ごとの合計が累計と合わなければ書き出せない。詳細: docs/design/actuals-export.md
import { useCallback, useEffect, useMemo, useState } from "react";
import { adminApi, type LineRow, useAdminCall } from "../adminApi";
import { at } from "../messages";
import { Feedback, useAdminList } from "../parts";
import { type ActualsRow, type Edits, mismatches, parseQty, quantitiesToSend, rowKey } from "./actuals";
import { ActualsTable } from "./ActualsTable";
import { ExportHistory } from "./ExportHistory";

const loadLines = () => adminApi.GET("/api/admin/lines");

export function ActualsPage() {
  const call = useAdminCall();
  const [workday, setWorkday] = useState<string | null>(null);
  useEffect(() => {
    void call(() => adminApi.GET("/api/admin/me")).then((r) => r.ok && setWorkday(r.data.workday));
  }, [call]);
  if (!workday) return <p className="admin-loading">{at("loading")}</p>;
  return <ActualsContent workday={workday} />;
}

type Filter = { from: string; to: string; lineCode: string };

function ActualsContent({ workday }: { workday: string }) {
  const call = useAdminCall();
  const { rows: lines, error: linesError } = useAdminList<LineRow>(loadLines);
  const [filter, setFilter] = useState<Filter>({ from: workday, to: workday, lineCode: "" });
  const [shown, setShown] = useState<Filter | null>(null); // 一覧を読んだときの条件(書き出しはこの条件で行う)
  const [rows, setRows] = useState<ActualsRow[] | null>(null);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);
  const [historyKey, setHistoryKey] = useState(0);

  const show = useCallback(async () => {
    const r = await call(() => adminApi.GET("/api/admin/actuals", {
      params: { query: { from: filter.from, to: filter.to, line_code: filter.lineCode || undefined } },
    }));
    setRows(r.ok ? r.data.rows : null);
    setShown(r.ok ? filter : null);
    setDrafts({});
    setMessage(r.ok ? null : { ok: false, text: r.message });
  }, [call, filter]);

  const { edits, invalid } = useMemo(() => {
    const e: Edits = {};
    let bad = false;
    for (const [key, text] of Object.entries(drafts)) {
      const q = parseQty(text);
      if (q === null) bad = true;
      else e[key] = q;
    }
    return { edits: e, invalid: bad };
  }, [drafts]);
  const problems = rows ? mismatches(rows, edits) : [];
  const exportable = rows?.filter((r) => r.exportable).length ?? 0;

  const doExport = async () => {
    if (!rows || !shown) return;
    const r = await call(() => adminApi.POST("/api/admin/actuals/export", {
      body: { date_from: shown.from, date_to: shown.to, line_code: shown.lineCode || null, quantities: quantitiesToSend(rows, edits) },
    }));
    setMessage(r.ok ? { ok: true, text: at("actuals.exported", { name: r.data.file_name, count: r.data.row_count }) } : { ok: false, text: r.message });
    if (r.ok) setHistoryKey((k) => k + 1);
  };

  return (
    <section aria-label={at("actuals.title")}>
      <h1>{at("actuals.title")}</h1>
      <p className="admin-note">{at("actuals.note")}</p>
      <div className="admin-add">
        <label className="admin-check">{at("actuals.from")}
          <input type="date" aria-label={at("actuals.from")} value={filter.from} onChange={(e) => setFilter({ ...filter, from: e.target.value })} />
        </label>
        <label className="admin-check">{at("actuals.to")}
          <input type="date" aria-label={at("actuals.to")} value={filter.to} onChange={(e) => setFilter({ ...filter, to: e.target.value })} />
        </label>
        <select aria-label={at("reports.line")} value={filter.lineCode} onChange={(e) => setFilter({ ...filter, lineCode: e.target.value })}>
          <option value="">{at("reports.allLines")}</option>
          {lines?.map((l) => <option key={l.line_code} value={l.line_code}>{at("lineOption", { name: l.name, code: l.line_code })}</option>)}
        </select>
        <button type="button" className="admin-btn" onClick={() => void show()}>{at("actuals.show")}</button>
      </div>
      <Feedback error={linesError} />
      {rows && rows.length === 0 && <p>{at("actuals.empty")}</p>}
      {rows && rows.length > 0 && (
        <>
          <ActualsTable rows={rows} drafts={drafts} edits={edits}
            onDraft={(r, text) => setDrafts({ ...drafts, [rowKey(r)]: text })} />
          {invalid && <p className="admin-error" role="alert">{at("actuals.badQty")}</p>}
          {problems.map((m) => (
            <p key={m.kitting_no} className="admin-error" role="alert">{at("actuals.mismatch", { kitting: m.kitting_no, sum: m.sum, total: m.total })}</p>
          ))}
          <div className="admin-add">
            <button type="button" className="admin-btn admin-primary" disabled={invalid || problems.length > 0 || exportable === 0}
              onClick={() => void doExport()}>{at("actuals.export")}</button>
            <span className="admin-note">{at("actuals.exportCount", { count: exportable })}</span>
          </div>
        </>
      )}
      <Feedback message={message} />
      <ExportHistory reloadKey={historyKey} />
    </section>
  );
}
