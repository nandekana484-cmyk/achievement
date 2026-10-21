// 作業者: 一覧を見るだけ(既存アプリから読み込む)。開発用の作業者だけは、既存アプリを読まない環境で追加できる。
import { type FormEvent, useState } from "react";
import { adminApi, type OperatorRow } from "./adminApi";
import { at } from "./messages";
import { Feedback, stateText, TextInput, useAdminList, useSave } from "./parts";

const loadOperators = () => adminApi.GET("/api/admin/operators");

export function OperatorsPage() {
  const { rows, error, reload } = useAdminList<OperatorRow>(loadOperators);
  const { save, message } = useSave(reload);
  const [draft, setDraft] = useState({ name: "", worker_id: "" });

  const add = async (e: FormEvent) => {
    e.preventDefault();
    const body = { name: draft.name, worker_id: draft.worker_id || null };
    if (await save(() => adminApi.POST("/api/admin/operators", { body }))) setDraft({ name: "", worker_id: "" });
  };

  return (
    <section aria-label={at("operators.title")}>
      <h1>{at("operators.title")}</h1>
      <p className="admin-note">{at("operators.note")}</p>
      <Feedback message={message} error={error} />
      <table className="admin-table">
        <thead>
          <tr>
            <th>{at("col.name")}</th><th>{at("col.workerId")}</th><th>{at("col.role")}</th>
            <th>{at("col.source")}</th><th>{at("col.password")}</th><th>{at("col.state")}</th>
          </tr>
        </thead>
        <tbody>
          {rows?.map((o) => (
            <tr key={o.id} className={o.active ? "" : "admin-inactive"}>
              <td>{o.name}</td><td>{o.worker_id ?? ""}</td>
              <td>{at(o.role === "admin" ? "role.admin" : "role.operator")}</td>
              <td>{at(o.source === "legacy" ? "source.legacy" : "source.local")}</td>
              <td>{o.role === "admin" ? at(o.has_password ? "password.set" : "password.unset") : ""}</td>
              <td>{stateText(o.active)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <form className="admin-add" onSubmit={add} aria-label={at("operators.addTitle")}>
        <h2>{at("operators.addTitle")}</h2>
        <TextInput label={at("col.name")} value={draft.name} onChange={(name) => setDraft({ ...draft, name })} required />
        <TextInput label={at("col.workerId")} value={draft.worker_id} onChange={(worker_id) => setDraft({ ...draft, worker_id })} />
        <button type="submit" className="admin-btn">{at("add")}</button>
      </form>
    </section>
  );
}
