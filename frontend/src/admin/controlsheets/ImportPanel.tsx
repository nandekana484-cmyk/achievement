// 管理表の内容の Excel 取り込み: ブックを選ぶ → 確かめるだけの結果(DBには書かない)→ 登録するシートを選んで「登録」。
// 登録のときは、同じブックをもう一度送る(サーバーはブックを残さないため)。詳細: docs/design/control-sheet.md
import { useCallback, useEffect, useRef, useState } from "react";
import type { components } from "../../api/schema";
import { useAdminCall } from "../adminApi";
import { ci } from "../messagesCsImport";
import { Feedback } from "../parts";
import { applyBody, applyMeta, BOOK_ACCEPT, carrySummary, defaultSelection, type ImportPreview, type ImportSheet, isRegisterable, overwriteCount, toggle } from "./importLogic";

type History = components["schemas"]["ImportHistoryOut"];
type Result = components["schemas"]["ImportResultOut"];
const BASE = "/api/admin/control-sheets";
const time = (iso: string) => iso.slice(0, 16).replace("T", " ");

/** 管理画面の API を呼ぶ(本文はブックそのもの)。X-Genba-Admin を付ける。useAdminCall が 401 と失敗の理由を扱う。 */
async function post(path: string, name: string, body: Blob) {
  const response = await fetch(`${BASE}${path}?filename=${encodeURIComponent(name)}`, { method: "POST", headers: { "X-Genba-Admin": "1", "Content-Type": "application/octet-stream" }, body });
  const json = await response.json().catch(() => null);
  return response.ok ? { data: json, response } : { error: json, response };
}

function Changes({ sheet }: { sheet: ImportSheet }) {
  if (sheet.status === "error" || sheet.status === "skipped") return <>{sheet.reason}</>;
  if (sheet.changes.length === 0 && sheet.carried === 0 && sheet.lost.length === 0) return null;
  const label = (c: ImportSheet["changes"][number]) => ci(`ci.field.${c.field}`, { row: c.row ?? "" });
  return (
    <details>
      <summary>
        {sheet.changes.length > 0 ? ci("ci.showChanges", { count: sheet.changes.length + sheet.changes_more }) : ci("ci.showCarry")}
        {sheet.carried > 0 && <span> {ci("ci.carried", { count: sheet.carried })}</span>}
        {sheet.lost.length > 0 && <span className="cs-overwrite"> {ci("ci.lostCount", { count: sheet.lost.length })}</span>}
      </summary>
      <ul className="cs-changes">
        {sheet.changes.map((c, i) => <li key={i}>{ci("ci.change", { label: label(c), before: c.before, after: c.after })}</li>)}
        {sheet.changes_more > 0 && <li>{ci("ci.changesMore", { count: sheet.changes_more })}</li>}
        {sheet.lost.map((x) => (
          <li key={`lost${x.row}`} className="cs-overwrite">
            {ci("ci.lost", { row: x.row, name: x.name, vi: x.name_vi ?? ci("ci.link.none"), link: ci(`ci.link.${x.link as "none" | "run1" | "run2" | "xray"}`) })}
          </li>
        ))}
      </ul>
    </details>
  );
}

function SheetRow({ sheet, selected, onToggle }: { sheet: ImportSheet; selected: boolean; onToggle: () => void }) {
  return (
    <tr className={`cs-import-${sheet.status}`}>
      <td>{isRegisterable(sheet) && <input type="checkbox" aria-label={ci("ci.col.pick") + " " + sheet.sheet_name} checked={selected} onChange={onToggle} />}</td>
      <td>{sheet.sheet_name}</td>
      <td>{sheet.file_no ?? ""}</td>
      <td>{ci(`ci.status.${sheet.status}`)}{sheet.overwrites_manual && <span className="cs-overwrite"> {ci("ci.overwrite")}</span>}</td>
      <td>{sheet.row_count ?? ""}</td>
      <td>{sheet.manager_no ?? ""}</td>
      <td><Changes sheet={sheet} /></td>
    </tr>
  );
}

export function ImportPanel({ onApplied }: { onApplied: () => void }) {
  const call = useAdminCall();
  const input = useRef<HTMLInputElement>(null);
  const [book, setBook] = useState<File | null>(null);
  const [preview, setPreview] = useState<ImportPreview | null>(null);
  const [selected, setSelected] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);
  const [history, setHistory] = useState<History[]>([]);

  const loadHistory = useCallback(() => {
    void call(() => fetch(`${BASE}/imports`).then(async (response) => ({ data: (await response.json().catch(() => null)) as History[] | null ?? undefined, response }))).then((r) => r.ok && Array.isArray(r.data) && setHistory(r.data));
  }, [call]);
  useEffect(loadHistory, [loadHistory]);

  const reset = () => { setBook(null); setPreview(null); setSelected([]); if (input.current) input.current.value = ""; };

  const choose = async (file: File | undefined) => {
    setMessage(null);
    setPreview(null);
    if (!file) return;
    if (!/\.(xls|xlsx|xlsm)$/i.test(file.name)) return setMessage({ ok: false, text: ci("ci.badBook") });
    setBook(file);
    setBusy(true);
    const r = await call(() => post("/import/preview", file.name, file) as Promise<{ data?: ImportPreview; error?: unknown; response: Response }>);
    setBusy(false);
    if (!r.ok) return setMessage({ ok: false, text: r.message });
    setPreview(r.data);
    setSelected(defaultSelection(r.data.sheets));
  };

  const apply = async () => {
    if (!book || !preview) return;
    setBusy(true);
    const r = await call(() => post("/import/apply", book.name, applyBody(applyMeta(preview, selected), book)) as Promise<{ data?: Result; error?: unknown; response: Response }>);
    setBusy(false);
    if (!r.ok) { // 確かめたブックと違う・確かめたあとに内容が変わった: 何も登録されていない。確かめ直してもらう
      setPreview(null);
      return setMessage({ ok: false, text: r.message });
    }
    setMessage({ ok: true, text: ci("ci.done", { count: r.data.registered, name: r.data.filename }) });
    reset();
    loadHistory();
    onApplied();
  };

  const sheets = preview?.sheets ?? [];
  const overwrites = overwriteCount(sheets, selected);
  const carry = carrySummary(sheets, selected);
  return (
    <section className="cs-import" aria-label={ci("ci.title")}>
      <h2>{ci("ci.title")}</h2>
      <p className="admin-note">{ci("ci.note")}</p>
      <label className="cs-file">
        {ci("ci.choose")}
        <input ref={input} type="file" accept={BOOK_ACCEPT} aria-label={ci("ci.choose")} disabled={busy} onChange={(e) => void choose(e.target.files?.[0])} />
      </label>
      {busy && book && !preview && <p role="status">{ci("ci.reading", { name: book.name })}</p>}
      <Feedback message={message} />
      {preview && (
        <div className="cs-preview">
          <h3>{ci("ci.result", { name: preview.filename })}</h3>
          <p>{ci("ci.counts", { new: preview.counts.new ?? 0, changed: preview.counts.changed ?? 0, unchanged: preview.counts.unchanged ?? 0, skipped: preview.counts.skipped ?? 0, error: preview.counts.error ?? 0 })}</p>
          {overwrites > 0 && <p className="admin-error" role="alert">{ci("ci.overwriteTotal", { count: overwrites })}</p>}
          {carry.carried + carry.lost > 0 && <p role="status">{ci("ci.carrySummary", { carried: carry.carried, lost: carry.lost })}</p>}
          <p>
            <button type="button" className="admin-btn" onClick={() => setSelected(defaultSelection(sheets))}>{ci("ci.selectAll")}</button>
            <button type="button" className="admin-btn" onClick={() => setSelected([])}>{ci("ci.selectNone")}</button>
          </p>
          <table className="admin-table" aria-label={ci("ci.result", { name: preview.filename })}>
            <thead>
              <tr>
                <th>{ci("ci.col.pick")}</th><th>{ci("ci.col.sheet")}</th><th>{ci("ci.col.fileNo")}</th><th>{ci("ci.col.status")}</th>
                <th>{ci("ci.col.rows")}</th><th>{ci("ci.col.manager")}</th><th>{ci("ci.col.reason")}</th>
              </tr>
            </thead>
            <tbody>
              {sheets.map((s, i) => <SheetRow key={`${s.sheet_name}:${i}`} sheet={s} selected={!!s.file_no && selected.includes(s.file_no)} onToggle={() => s.file_no && setSelected(toggle(sheets, selected, s.file_no))} />)}
            </tbody>
          </table>
          <p>
            <button type="button" className="admin-btn admin-primary" disabled={busy || selected.length === 0} onClick={() => void apply()}>{ci("ci.apply", { count: selected.length })}</button>
            <button type="button" className="admin-btn" disabled={busy} onClick={reset}>{ci("ci.cancel")}</button>
            {defaultSelection(sheets).length === 0 && <span> {ci("ci.nothingToRegister")}</span>}
          </p>
        </div>
      )}
      <h3>{ci("ci.history")}</h3>
      {history.length === 0 ? <p>{ci("ci.history.empty")}</p> : (
        <table className="admin-table" aria-label={ci("ci.history")}>
          <thead><tr><th>{ci("ci.history.col.at")}</th><th>{ci("ci.history.col.by")}</th><th>{ci("ci.history.col.book")}</th><th>{ci("ci.history.col.sheets")}</th><th>{ci("ci.history.col.count")}</th></tr></thead>
          <tbody>
            {history.map((h) => <tr key={h.id}><td>{time(h.imported_at)}</td><td>{h.imported_by_name ?? ""}</td><td>{h.filename}</td><td>{h.sheet_count}</td><td>{h.registered_count}</td></tr>)}
          </tbody>
        </table>
      )}
    </section>
  );
}
