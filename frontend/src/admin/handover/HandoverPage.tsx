// 引き継ぎの確認: 実績のある計画が、出し直しで取り消された・古くなったとき、実績を新しいキッティングNo.へ移す。
// 自動では移さない。管理者が移す先を選んで確定する(確認のダイアログつき)。詳細: docs/design/legacy-integration.md
import { useCallback, useEffect, useState } from "react";
import type { components } from "../../api/schema";
import { ConfirmDialog } from "../ConfirmDialog";
import { adminApi, useAdminCall } from "../adminApi";
import { type AdminKey, at } from "../messages";
import { Feedback } from "../parts";

type List = components["schemas"]["HandoverListOut"];
type Item = components["schemas"]["HandoverItemOut"];
type Target = components["schemas"]["TargetOut"];
type Option = { kitting_no: string; from_legacy: boolean; has_actuals: boolean };

const time = (iso: string) => iso.slice(0, 16).replace("T", " ");

export function HandoverPage() {
  const call = useAdminCall();
  const [data, setData] = useState<List | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [choice, setChoice] = useState<Record<string, string>>({});
  const [asking, setAsking] = useState<{ item: Item; target: string | null } | null>(null);
  const [found, setFound] = useState<Record<string, Target[]>>({});
  const [result, setResult] = useState<{ ok: boolean; text: string; warnings: string[] } | null>(null);

  const load = useCallback(() => {
    void call(() => adminApi.GET("/api/admin/handovers")).then((r) => (r.ok ? setData(r.data) : setError(r.message)));
  }, [call]);
  useEffect(load, [load]);

  // 移す先の選択肢: 候補と、手で探した有効な計画
  const options = (item: Item): Option[] => [
    ...item.candidates,
    ...(found[item.kitting_no] ?? []).filter((t) => !item.candidates.some((c) => c.kitting_no === t.kitting_no))
      .map((t) => ({ kitting_no: t.kitting_no, from_legacy: false, has_actuals: t.has_actuals })),
  ];
  const target = (item: Item) => choice[item.kitting_no] ?? options(item).find((c) => !c.has_actuals)?.kitting_no ?? "";
  const search = async (item: Item, q: string) => {
    if (!q.trim()) return setFound({ ...found, [item.kitting_no]: [] });
    const r = await call(() => adminApi.GET("/api/admin/handovers/targets", { params: { query: { q: q.trim(), exclude: item.kitting_no } } }));
    if (r.ok) setFound({ ...found, [item.kitting_no]: r.data });
  };
  const confirm = async () => {
    if (!asking) return;
    const { item, target: to } = asking;
    setAsking(null);
    const r = to
      ? await call(() => adminApi.POST("/api/admin/handovers/confirm", { body: { old_kitting_no: item.kitting_no, new_kitting_no: to } }))
      : await call(() => adminApi.POST("/api/admin/handovers/decline", { body: { old_kitting_no: item.kitting_no } }));
    if (r.ok) setResult({ ok: true, text: at(to ? "handover.done" : "handover.declined", { from: item.kitting_no, to: to ?? "" }), warnings: r.data.warnings });
    else setResult({ ok: false, text: r.message, warnings: [] });
    if (r.ok) load();
  };

  if (!data) return <p className="admin-loading">{error ?? at("loading")}</p>;
  return (
    <section aria-label={at("handover.title")}>
      <h1>{at("handover.title")}</h1>
      <p className="admin-note">{at("handover.note")}</p>
      <Feedback message={result && { ok: result.ok, text: result.text }} error={error} />
      {result?.warnings.map((w) => <p key={w} className="admin-error" role="alert">{w}</p>)}
      {data.items.length === 0 ? <p>{at("handover.empty")}</p> : (
        <table className="admin-table" aria-label={at("handover.title")}>
          <thead>
            <tr>
              <th>{at("handover.col.kitting")}</th><th>{at("handover.col.reason")}</th><th>{at("handover.col.target")}</th><th>{at("col.actions")}</th>
            </tr>
          </thead>
          <tbody>
            {data.items.map((i) => (
              <tr key={i.kitting_no}>
                <td>
                  {i.kitting_no}
                  <span className="admin-code"> {at("handover.plan", { file: i.file_no, line: i.line_code, run: i.run_no, lots: i.lot_nos.join(at("listSeparator")) })}</span>
                </td>
                <td>
                  {at(`handover.reason.${i.reason}` as AdminKey)}
                  {i.completed && <span className="admin-code"> {at("handover.completed")}</span>}
                  {i.replacement_count >= 2 && <span className="admin-error"> {at("handover.multi", { count: i.replacement_count })}</span>}
                </td>
                <td>
                  {options(i).length === 0 && <span>{at("handover.noCandidate")}</span>}
                  <input aria-label={at("handover.search", { kitting: i.kitting_no })} placeholder={at("handover.searchHint")}
                    onChange={(e) => void search(i, e.target.value)} />
                  {options(i).length > 0 && (
                    <select aria-label={at("handover.pick", { kitting: i.kitting_no })} value={target(i)}
                      onChange={(e) => setChoice({ ...choice, [i.kitting_no]: e.target.value })}>
                      {options(i).map((c) => (
                        <option key={c.kitting_no} value={c.kitting_no} disabled={c.has_actuals}>
                          {c.kitting_no}{c.from_legacy ? at("handover.fromLegacy") : ""}{c.has_actuals ? at("handover.hasActuals") : ""}
                        </option>
                      ))}
                    </select>
                  )}
                </td>
                <td>
                  <button type="button" className="admin-btn" disabled={!target(i)} onClick={() => setAsking({ item: i, target: target(i) })}>
                    {at("handover.confirm")}
                  </button>
                  <button type="button" className="admin-btn" onClick={() => setAsking({ item: i, target: null })}>{at("handover.decline")}</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <h2>{at("handover.history")}</h2>
      {data.history.length === 0 ? <p>{at("handover.noHistory")}</p> : (
        <table className="admin-table" aria-label={at("handover.history")}>
          <thead>
            <tr><th>{at("handover.col.at")}</th><th>{at("handover.col.from")}</th><th>{at("handover.col.to")}</th><th>{at("handover.col.by")}</th><th>{at("handover.col.moved")}</th></tr>
          </thead>
          <tbody>
            {data.history.map((h) => (
              <tr key={h.id}>
                <td>{time(h.confirmed_at)}</td><td>{h.old_kitting_no}</td><td>{h.new_kitting_no ?? at("handover.declinedLabel")}</td><td>{h.confirmed_by}</td>
                <td>{Object.entries(h.moved).map(([k, n]) => `${k} ${n}`).join(at("listSeparator"))}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {asking && (
        <ConfirmDialog message={asking.target ? at("handover.ask", { from: asking.item.kitting_no, to: asking.target }) : at("handover.askDecline", { from: asking.item.kitting_no })}
          confirmLabel={at(asking.target ? "handover.confirm" : "handover.decline")}
          cancelLabel={at("access.confirm.cancel")} onConfirm={() => void confirm()} onCancel={() => setAsking(null)} />
      )}
    </section>
  );
}
