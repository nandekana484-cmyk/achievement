// 実績の書き出しの履歴(いつ・誰が・何行・ファイル名)と、書き出した CSV のダウンロード。
import { useCallback, useEffect, useState } from "react";
import type { components } from "../../api/schema";
import { adminApi, useAdminCall } from "../adminApi";
import { filenameOf, saveBlob } from "../download";
import { at } from "../messages";
import { Feedback } from "../parts";

type ExportRow = components["schemas"]["ExportOut"];

const time = (iso: string) => iso.slice(0, 19).replace("T", " ");

export function ExportHistory({ reloadKey }: { reloadKey: number }) {
  const call = useAdminCall();
  const [rows, setRows] = useState<ExportRow[] | null>(null);
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);

  const load = useCallback(() => {
    void call(() => adminApi.GET("/api/admin/actuals/exports")).then((r) => (r.ok ? setRows(r.data) : setMessage({ ok: false, text: r.message })));
  }, [call]);
  useEffect(load, [load, reloadKey]);

  const download = async (row: ExportRow) => {
    let name = row.file_name;
    const r = await call(async () => {
      const res = await adminApi.GET("/api/admin/actuals/exports/{export_id}/file", {
        params: { path: { export_id: row.id } }, parseAs: "blob",
      });
      name = filenameOf(res.response, name);
      return res;
    });
    if (!r.ok) return setMessage({ ok: false, text: r.message });
    saveBlob(r.data as Blob, name);
    setMessage({ ok: true, text: at("actuals.downloaded", { name }) });
  };

  return (
    <div className="actuals-history">
      <h2>{at("actuals.historyTitle")}</h2>
      <Feedback message={message} />
      {rows?.length === 0 && <p className="admin-note">{at("actuals.history.empty")}</p>}
      {rows && rows.length > 0 && (
        <table className="admin-table" aria-label={at("actuals.historyTitle")}>
          <thead>
            <tr>
              <th>{at("actuals.history.at")}</th><th>{at("actuals.history.by")}</th><th>{at("actuals.history.rows")}</th>
              <th>{at("actuals.history.file")}</th><th>{at("actuals.history.period")}</th><th>{at("actuals.history.line")}</th><th />
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id}>
                <td>{time(r.exported_at)}</td><td>{r.exported_by}</td><td>{r.row_count}</td><td>{r.file_name}</td>
                <td>{`${r.date_from} - ${r.date_to}`}</td><td>{r.line_code ?? at("reports.allLines")}</td>
                <td><button type="button" className="admin-btn" onClick={() => void download(r)}>{at("actuals.history.download")}</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
