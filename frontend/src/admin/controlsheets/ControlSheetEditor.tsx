// 管理表の内容の編集: 管理No と工程の行(追加・削除・並べ替え)を直して保存する。保存のたびに新しい版を足す。前の版は履歴から読み込める。
import { useCallback, useEffect, useState } from "react";
import type { components } from "../../api/schema";
import { adminApi, useAdminCall } from "../adminApi";
import { ct } from "../messagesControlSheet";
import { Feedback } from "../parts";
import { addRow, KINDS, LINKS, moveRow, removeRow, type Row, toPayload, tooManyRows, updateRow } from "./rowsEdit";

type Sheet = components["schemas"]["ControlSheetOut"];
const time = (iso: string) => iso.slice(0, 16).replace("T", " ");

function RowEditor({ row, no, last, onChange, onMove, onRemove, onInsert }: {
  row: Row; no: number; last: boolean; onChange: (patch: Partial<Row>) => void; onMove: (dir: -1 | 1) => void; onRemove: () => void; onInsert: () => void;
}) {
  return (
    <li className="cs-row" aria-label={ct("cs.rowTitle", { no })}>
      <div className="cs-row-head">
        <strong>{ct("cs.rowTitle", { no })}</strong>
        <button type="button" className="admin-btn" disabled={no === 1} onClick={() => onMove(-1)}>{ct("cs.up")}</button>
        <button type="button" className="admin-btn" disabled={last} onClick={() => onMove(1)}>{ct("cs.down")}</button>
        <button type="button" className="admin-btn" onClick={onInsert}>{ct("cs.insertBelow")}</button>
        <button type="button" className="admin-btn" onClick={onRemove}>{ct("cs.remove")}</button>
      </div>
      <div className="cs-row-grid">
        <label>{ct("cs.name")}<input value={row.name} maxLength={100} onChange={(e) => onChange({ name: e.target.value })} /></label>
        <label>{ct("cs.nameVi")}<input value={row.name_vi ?? ""} maxLength={200} onChange={(e) => onChange({ name_vi: e.target.value })} /></label>
        <label>{ct("cs.kind")}
          <select value={row.kind} onChange={(e) => onChange({ kind: e.target.value as Row["kind"] })}>
            {KINDS.map((k) => <option key={k} value={k}>{ct(`cs.kind.${k}`)}</option>)}
          </select>
        </label>
        <label>{ct("cs.link")}
          <select value={row.link} onChange={(e) => onChange({ link: e.target.value as Row["link"] })}>
            {LINKS.map((k) => <option key={k} value={k}>{ct(`cs.link.${k}`)}</option>)}
          </select>
        </label>
        <label className="cs-wide">{ct("cs.procedure")}<textarea rows={3} value={row.procedure} maxLength={2000} onChange={(e) => onChange({ procedure: e.target.value })} /></label>
        <label className="cs-check"><input type="checkbox" checked={row.use_line} onChange={(e) => onChange({ use_line: e.target.checked })} />{ct("cs.useLine")}</label>
      </div>
    </li>
  );
}

export function ControlSheetEditor({ fileNo, onBack, onSaved }: { fileNo: string; onBack: () => void; onSaved: () => void }) {
  const call = useAdminCall();
  const [managerNo, setManagerNo] = useState("");
  const [rows, setRows] = useState<Row[]>([]);
  const [history, setHistory] = useState<Sheet[]>([]);
  const [ready, setReady] = useState(false);
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);

  const load = useCallback(() => {
    void call(() => adminApi.GET("/api/admin/control-sheets/{file_no}/history", { params: { path: { file_no: fileNo } } })).then((r) => {
      if (!r.ok) return setMessage({ ok: false, text: r.message });
      setHistory(r.data);
      if (r.data[0]) { setManagerNo(r.data[0].manager_no); setRows(r.data[0].rows); }
      setReady(true);
    });
  }, [call, fileNo]);
  useEffect(load, [load]);

  const save = async () => {
    const r = await call(() => adminApi.PUT("/api/admin/control-sheets/{file_no}", { params: { path: { file_no: fileNo } }, body: { manager_no: managerNo, rows: toPayload(rows) } }));
    if (!r.ok) return setMessage({ ok: false, text: r.message });
    setMessage({ ok: true, text: ct("cs.saved", { version: r.data.version }) });
    load();
    onSaved();
  };
  const loadVersion = (v: Sheet) => {
    setManagerNo(v.manager_no);
    setRows(v.rows);
    setMessage({ ok: true, text: ct("cs.loaded", { version: v.version }) });
  };

  if (!ready) return <p className="admin-loading">{message?.text ?? "…"}</p>;
  return (
    <section aria-label={ct("cs.editorTitle", { file: fileNo })}>
      <h1>{ct("cs.editorTitle", { file: fileNo })}</h1>
      <button type="button" className="admin-btn" onClick={onBack}>{ct("cs.back")}</button>
      <Feedback message={message} />
      <label className="cs-manager">{ct("cs.managerNo")}
        <input aria-label={ct("cs.managerNo")} value={managerNo} maxLength={50} onChange={(e) => setManagerNo(e.target.value)} />
      </label>
      <h2>{ct("cs.rows")}</h2>
      {rows.length === 0 && <p>{ct("cs.noRows")}</p>}
      {tooManyRows(rows) && <p className="admin-error" role="status">{ct("cs.manyRows", { count: rows.length })}</p>}
      <ol className="cs-rows">
        {rows.map((r, i) => (
          <RowEditor key={i} row={r} no={i + 1} last={i === rows.length - 1}
            onChange={(patch) => setRows(updateRow(rows, i, patch))} onMove={(d) => setRows(moveRow(rows, i, d))}
            onRemove={() => setRows(removeRow(rows, i))} onInsert={() => setRows(addRow(rows, i))} />
        ))}
      </ol>
      <p>
        <button type="button" className="admin-btn" onClick={() => setRows(addRow(rows))}>{ct("cs.addRow")}</button>
        <button type="button" className="admin-btn admin-primary" onClick={() => void save()}>{ct("cs.save")}</button>
      </p>
      {history.length > 0 && (
        <>
          <h2>{ct("cs.history")}</h2>
          <ul className="cs-history">
            {history.map((v) => (
              <li key={v.version}>
                {ct("cs.historyRow", { version: v.version, when: time(v.saved_at), who: v.saved_by_name ?? "", copied: v.copied_from ? ct("cs.copiedFrom", { file: v.copied_from }) : "" })}{" "}
                <button type="button" className="admin-btn" onClick={() => loadVersion(v)}>{ct("cs.loadVersion")}</button>
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}
