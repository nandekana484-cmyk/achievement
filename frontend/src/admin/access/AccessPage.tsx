// アクセス制限: 登録したIPアドレスからだけ、画面とAPIを使えるようにする。一覧、追加、無効化、今の接続元が許可されているか。
// 今の接続元が許可から外れる変更は、サーバーが断る(理由の文をそのまま出す)。詳細: docs/design/security.md
import { type FormEvent, useCallback, useEffect, useState } from "react";
import { adminApi, useAdminCall } from "../adminApi";
import { at } from "../messages";
import { ConfirmDialog } from "../ConfirmDialog";
import { Feedback, TextInput, useSave } from "../parts";
import { type AccessInfo, alreadyListed, emptyingWarning, looksLikeNetwork, type NetworkRow, type Scope, summarize } from "./accessLogic";

const time = (iso: string) => iso.slice(0, 16).replace("T", " ");
const scopeText = (scope: Scope) => at(scope === "field" ? "access.scope.field" : "access.scope.admin");
const canUse = (ok: boolean) => at(ok ? "access.can" : "access.cannot");

function useAccess() {
  const call = useAdminCall();
  const [info, setInfo] = useState<AccessInfo | null>(null);
  const [error, setError] = useState<string | null>(null);
  const reload = useCallback(() => {
    void call(() => adminApi.GET("/api/admin/access")).then((r) => (r.ok ? setInfo(r.data) : setError(r.message)));
  }, [call]);
  useEffect(reload, [reload]);
  return { info, error, reload };
}

export function AccessPage() {
  const { info, error, reload } = useAccess();
  const { save, message } = useSave(reload);
  const [scope, setScope] = useState<Scope>("field");
  const [network, setNetwork] = useState("");
  const [note, setNote] = useState("");
  const [invalid, setInvalid] = useState(false);

  const add = (value: string, memo: string) =>
    save(() => adminApi.POST("/api/admin/access/networks", { body: { network: value, scope, note: memo || null } }));
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    const ok = looksLikeNetwork(network);
    setInvalid(!ok);
    if (ok && (await add(network.trim(), note))) {
      setNetwork("");
      setNote("");
    }
  };
  const [confirming, setConfirming] = useState<{ row: NetworkRow; message: string } | null>(null);
  const disable = (row: NetworkRow) =>
    save(() => adminApi.POST("/api/admin/access/networks/{network_id}/disable", { params: { path: { network_id: row.id } } }));
  // 一覧が空になる(制限がなくなる、または広がる)変更は、確認してから送る
  const askDisable = (row: NetworkRow) => {
    const warning = info && emptyingWarning(info, row);
    if (warning) setConfirming({ row, message: at(warning) });
    else void disable(row);
  };

  if (!info) return <p className="admin-loading">{error ?? at("loading")}</p>;
  const sum = summarize(info);
  return (
    <section aria-label={at("access.title")}>
      <h1>{at("access.title")}</h1>
      <p className="admin-note">{at("access.note")}</p>
      <Feedback message={message} error={error} />

      <div className="admin-status" role="group" aria-label={at("access.statusTitle")}>
        <p><strong>{at(info.my_ip_is_loopback ? "access.me.loopback" : "access.me", { ip: info.my_ip })}</strong></p>
        <p>{at(sum.fieldRestricted ? "access.field.on" : "access.field.off", { count: sum.fieldCount })}</p>
        <p>{at(sum.adminRestricted ? "access.admin.on" : "access.admin.same", { count: sum.adminCount })}</p>
        <p>{at("access.mine.field", { state: canUse(info.field_allowed) })}</p>
        <p>{at("access.mine.admin", { state: canUse(info.admin_allowed) })}</p>
      </div>

      <form className="admin-inline-form" onSubmit={submit} aria-label={at("access.addTitle")}>
        <label>{at("access.scope")}
          <select value={scope} onChange={(e) => setScope(e.target.value as Scope)}>
            <option value="field">{at("access.scope.field")}</option>
            <option value="admin">{at("access.scope.admin")}</option>
          </select>
        </label>
        <TextInput label={at("access.network")} value={network} onChange={(v) => { setNetwork(v); setInvalid(false); }} required />
        <TextInput label={at("access.memo")} value={note} onChange={setNote} />
        <button type="submit" className="admin-btn admin-primary">{at("add")}</button>
        <button type="button" className="admin-btn" disabled={alreadyListed(info, scope)}
          onClick={() => void add(info.my_ip, at("access.memo.mine"))}>
          {at("access.addMine")}
        </button>
      </form>
      <p className="admin-note">{at("access.hint")}</p>
      {invalid && <p className="admin-error" role="alert">{at("access.invalid")}</p>}

      <table className="admin-table">
        <thead>
          <tr>
            <th>{at("access.scope")}</th><th>{at("access.col.network")}</th><th>{at("access.memo")}</th><th>{at("access.col.by")}</th>
            <th>{at("access.col.at")}</th><th>{at("col.state")}</th><th>{at("col.actions")}</th>
          </tr>
        </thead>
        <tbody>
          {info.networks.length === 0 && <tr><td colSpan={7}>{at("access.empty")}</td></tr>}
          {info.networks.map((r) => (
            <tr key={r.id} className={r.active ? "" : "admin-inactive"}>
              <td>{scopeText(r.scope)}</td><td>{r.network}</td><td>{r.note ?? ""}</td><td>{r.created_by ?? at("access.byServer")}</td>
              <td>{time(r.created_at)}</td>
              <td>{r.active ? at("active") : at("access.disabledAt", { at: r.disabled_at ? time(r.disabled_at) : "" })}</td>
              <td>{r.active && <button type="button" className="admin-btn" onClick={() => askDisable(r)}>{at("deactivate")}</button>}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {confirming && (
        <ConfirmDialog
          message={confirming.message} confirmLabel={at("access.confirm.ok")} cancelLabel={at("access.confirm.cancel")}
          onCancel={() => setConfirming(null)}
          onConfirm={() => { const { row } = confirming; setConfirming(null); void disable(row); }}
        />
      )}
    </section>
  );
}
