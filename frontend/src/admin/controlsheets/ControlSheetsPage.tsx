// 管理表の内容(K社製品ロット管理票のファイルNo.ごとの内容): 一覧(登録済みと、今の計画にあって未登録のファイルNo.)と、新しい登録(コピー元を選べる)。
import { useCallback, useState } from "react";
import type { components } from "../../api/schema";
import { adminApi } from "../adminApi";
import { ct } from "../messagesControlSheet";
import { Feedback, useAdminList, useSave } from "../parts";
import { ControlSheetEditor } from "./ControlSheetEditor";
import { ImportPanel } from "./ImportPanel";

type Summary = components["schemas"]["ControlSheetSummaryOut"];
const time = (iso: string) => iso.slice(0, 16).replace("T", " ");

export function ControlSheetsPage() {
  const load = useCallback(() => adminApi.GET("/api/admin/control-sheets"), []);
  const { rows, error, reload } = useAdminList<Summary>(load);
  const { save, message } = useSave(reload);
  const [editing, setEditing] = useState<string | null>(null);
  const [fileNo, setFileNo] = useState("");
  const [source, setSource] = useState("");
  const [localError, setLocalError] = useState<string | null>(null);

  if (editing) return <ControlSheetEditor fileNo={editing} onBack={() => setEditing(null)} onSaved={reload} />;

  const create = async () => {
    const key = fileNo.trim();
    if (!key) return setLocalError(ct("cs.needFileNo"));
    setLocalError(null);
    if (!source) return setEditing(key);
    const ok = await save(() => adminApi.POST("/api/admin/control-sheets/{file_no}/copy", { params: { path: { file_no: key } }, body: { source_file_no: source } }), ct("cs.saved", { version: 1 }));
    if (ok) setEditing(key);
  };

  return (
    <section aria-label={ct("cs.title")}>
      <h1>{ct("cs.title")}</h1>
      <p className="admin-note">{ct("cs.note")}</p>
      <Feedback message={message} error={error ?? localError} />
      <ImportPanel onApplied={reload} />
      <form className="admin-add" aria-label={ct("cs.newTitle")} onSubmit={(e) => { e.preventDefault(); void create(); }}>
        <h2>{ct("cs.newTitle")}</h2>
        <input aria-label={ct("cs.fileNo")} placeholder={ct("cs.fileNo")} value={fileNo} maxLength={20} onChange={(e) => setFileNo(e.target.value)} />
        <select aria-label={ct("cs.copyFrom")} value={source} onChange={(e) => setSource(e.target.value)}>
          <option value="">{ct("cs.copyNone")}</option>
          {rows?.filter((r) => r.registered).map((r) => <option key={r.file_no} value={r.file_no}>{r.file_no}</option>)}
        </select>
        <button type="submit" className="admin-btn admin-primary">{ct("cs.create")}</button>
      </form>
      {rows && rows.length === 0 && <p>{ct("cs.empty")}</p>}
      {rows && rows.length > 0 && (
        <table className="admin-table" aria-label={ct("cs.title")}>
          <thead>
            <tr>
              <th>{ct("cs.col.fileNo")}</th><th>{ct("cs.col.product")}</th><th>{ct("cs.col.state")}</th><th>{ct("cs.col.manager")}</th>
              <th>{ct("cs.col.rows")}</th><th>{ct("cs.col.version")}</th><th>{ct("cs.col.savedBy")}</th><th>{ct("cs.col.savedAt")}</th><th />
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.file_no} className={r.registered ? "" : "cs-unregistered"}>
                <td>{r.file_no}</td>
                <td>{r.product_name ?? ""}</td>
                <td>{r.registered ? ct("cs.registered") : ct("cs.unregistered")}</td>
                <td>{r.manager_no ?? ""}</td>
                <td>{r.row_count ?? ""}</td>
                <td>{r.version ?? ""}</td>
                <td>{r.saved_by_name ?? ""}</td>
                <td>{r.saved_at ? time(r.saved_at) : ""}</td>
                <td><button type="button" className="admin-btn" onClick={() => setEditing(r.file_no)}>{r.registered ? ct("cs.edit") : ct("cs.register")}</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
