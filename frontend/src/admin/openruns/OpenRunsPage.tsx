// 終了していない古い記録: ライン画面の表示範囲を広げても入らない、終了のない工程の記録。管理者が、終了の時刻を入れるか取り消す。
// どちらも確認のダイアログつき。訂正の履歴(run_corrections。source=admin)と変更の記録(audit_log)に残る。詳細: docs/design/run-records.md
import { useCallback, useEffect, useState } from "react";
import type { components } from "../../api/schema";
import { ConfirmDialog } from "../ConfirmDialog";
import { adminApi, useAdminCall } from "../adminApi";
import { at } from "../messages";
import { Feedback } from "../parts";

type Row = components["schemas"]["OpenRunOut"];
type Line = components["schemas"]["LineAdminOut"];
type Draft = { endAt: string; qty: string; reason: string; note: string };
type Asking = { row: Row; kind: "end" | "void" };

const EMPTY: Draft = { endAt: "", qty: "", reason: "forgot", note: "" };
const time = (iso: string) => iso.slice(0, 16).replace("T", " ");
const toJstIso = (local: string) => `${local}:00+09:00`; // datetime-local の値(日本時間)

export function OpenRunsPage() {
  const call = useAdminCall();
  const [rows, setRows] = useState<Row[] | null>(null);
  const [lines, setLines] = useState<Line[]>([]);
  const [line, setLine] = useState("");
  const [drafts, setDrafts] = useState<Record<number, Draft>>({});
  const [asking, setAsking] = useState<Asking | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);

  const load = useCallback(() => {
    const query = line ? { line_code: line } : {};
    void call(() => adminApi.GET("/api/admin/open-runs", { params: { query } })).then((r) => (r.ok ? setRows(r.data) : setError(r.message)));
  }, [call, line]);
  useEffect(load, [load]);
  useEffect(() => {
    void call(() => adminApi.GET("/api/admin/lines")).then((r) => r.ok && setLines(r.data));
  }, [call]);

  const draft = (id: number) => drafts[id] ?? EMPTY;
  const patch = (id: number, next: Partial<Draft>) => setDrafts({ ...drafts, [id]: { ...draft(id), ...next } });

  const send = async () => {
    if (!asking) return;
    const { row, kind } = asking;
    const d = draft(row.id);
    setAsking(null);
    const params = { path: { event_id: row.id } };
    const common = { reason: d.reason, note: d.note.trim() || null };
    const r = kind === "end"
      ? await call(() => adminApi.POST("/api/admin/open-runs/{event_id}/end", {
        params, body: { ...common, end_at: toJstIso(d.endAt), produced_qty: row.step_type === "production" && d.qty !== "" ? Number(d.qty) : null },
      }))
      : await call(() => adminApi.POST("/api/admin/open-runs/{event_id}/void", { params, body: common }));
    const vars = { kitting: row.kitting_no, step: row.step_label };
    if (r.ok) {
      setMessage({ ok: true, text: at(kind === "void" ? "openRuns.doneVoid" : r.data.completed && row.step_type === "cleanup" ? "openRuns.doneEndCleanup" : "openRuns.doneEnd", vars) });
      load();
    } else setMessage({ ok: false, text: r.message });
  };

  if (!rows) return <p className="admin-loading">{error ?? at("loading")}</p>;
  const askText = asking && at(
    asking.kind === "void" ? "openRuns.askVoid" : asking.row.step_type === "cleanup" ? "openRuns.askEndCleanup" : "openRuns.askEnd",
    { kitting: asking.row.kitting_no, step: asking.row.step_label, start: time(asking.row.start_at), end: draft(asking.row.id).endAt.replace("T", " ") },
  );
  return (
    <section aria-label={at("openRuns.title")}>
      <h1>{at("openRuns.title")}</h1>
      <p className="admin-note">{at("openRuns.note")}</p>
      <label>
        {at("openRuns.line")}{" "}
        <select aria-label={at("openRuns.line")} value={line} onChange={(e) => setLine(e.target.value)}>
          <option value="">{at("openRuns.lineAll")}</option>
          {lines.map((l) => <option key={l.line_code} value={l.line_code}>{l.line_code}</option>)}
        </select>
      </label>
      <Feedback message={message} error={error} />
      {rows.length === 0 ? <p>{at("openRuns.empty")}</p> : (
        <table className="admin-table" aria-label={at("openRuns.title")}>
          <thead>
            <tr>
              <th>{at("openRuns.col.line")}</th><th>{at("openRuns.col.kitting")}</th><th>{at("openRuns.col.step")}</th>
              <th>{at("openRuns.col.start")}</th><th>{at("openRuns.col.by")}</th><th>{at("col.actions")}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => {
              const d = draft(r.id);
              const who = { kitting: r.kitting_no, step: r.step_label };
              return (
                <tr key={r.id}>
                  <td>{r.line_code}</td>
                  <td>{r.kitting_no}<span className="admin-code"> {r.product_name}</span></td>
                  <td>{r.step_label}</td>
                  <td>{time(r.start_at)}</td>
                  <td>{r.started_by_name ?? ""}</td>
                  <td>
                    <input type="datetime-local" aria-label={at("openRuns.endAt", who)} value={d.endAt} onChange={(e) => patch(r.id, { endAt: e.target.value })} />
                    {r.step_type === "production" && (
                      <input type="number" min={0} aria-label={at("openRuns.qty", who)} placeholder={at("openRuns.qty", who)} value={d.qty} onChange={(e) => patch(r.id, { qty: e.target.value })} />
                    )}
                    <select aria-label={at("openRuns.reason", who)} value={d.reason} onChange={(e) => patch(r.id, { reason: e.target.value })}>
                      {(["forgot", "mistake", "other"] as const).map((k) => <option key={k} value={k}>{at(`openRuns.reason.${k}`)}</option>)}
                    </select>
                    <input aria-label={at("openRuns.note.label", who)} placeholder={at("openRuns.note.label", who)} maxLength={100} value={d.note} onChange={(e) => patch(r.id, { note: e.target.value })} />
                    <button type="button" className="admin-btn" disabled={!d.endAt} title={d.endAt ? "" : at("openRuns.needEnd")} onClick={() => setAsking({ row: r, kind: "end" })}>
                      {at("openRuns.end")}
                    </button>
                    <button type="button" className="admin-btn" onClick={() => setAsking({ row: r, kind: "void" })}>{at("openRuns.void")}</button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
      {asking && askText && (
        <ConfirmDialog message={askText} confirmLabel={at(asking.kind === "end" ? "openRuns.end" : "openRuns.void")}
          cancelLabel={at("access.confirm.cancel")} onConfirm={() => void send()} onCancel={() => setAsking(null)} />
      )}
    </section>
  );
}
