// ライン: 一覧、名前と並び順の変更、無効化(消さない)。ラインは計画の同期で自動で登録される。
import { useState } from "react";
import { adminApi, type LineRow } from "./adminApi";
import { at } from "./messages";
import { Feedback, NumberInput, stateText, TextInput, useAdminList, useSave, yesNo } from "./parts";

const loadLines = () => adminApi.GET("/api/admin/lines");

export function LinesPage() {
  const { rows, error, reload } = useAdminList<LineRow>(loadLines);
  const { save, message } = useSave(reload);
  const [editing, setEditing] = useState<LineRow | null>(null);

  const patch = (code: string, body: Partial<LineRow>) =>
    save(() => adminApi.PATCH("/api/admin/lines/{line_code}", { params: { path: { line_code: code } }, body }));
  const saveEdit = async () => {
    if (editing && (await patch(editing.line_code, { name: editing.name, sort_order: editing.sort_order }))) setEditing(null);
  };

  return (
    <section aria-label={at("lines.title")}>
      <h1>{at("lines.title")}</h1>
      <p className="admin-note">{at("lines.note")}</p>
      <Feedback message={message} error={error} />
      <table className="admin-table">
        <thead>
          <tr>
            <th>{at("col.code")}</th><th>{at("col.name")}</th><th>{at("col.autoNamed")}</th>
            <th>{at("col.sort")}</th><th>{at("col.state")}</th><th>{at("col.actions")}</th>
          </tr>
        </thead>
        <tbody>
          {rows?.map((r) => editing?.line_code === r.line_code ? (
            <tr key={r.line_code} className="admin-editing">
              <td>{r.line_code}</td>
              <td><TextInput label={at("col.name")} value={editing.name} onChange={(name) => setEditing({ ...editing, name })} /></td>
              <td>{yesNo(r.auto_named)}</td>
              <td><NumberInput label={at("col.sort")} value={editing.sort_order} onChange={(sort_order) => setEditing({ ...editing, sort_order })} /></td>
              <td>{stateText(r.active)}</td>
              <td>
                <button type="button" className="admin-btn admin-primary" onClick={() => void saveEdit()}>{at("save")}</button>
                <button type="button" className="admin-btn" onClick={() => setEditing(null)}>{at("cancel")}</button>
              </td>
            </tr>
          ) : (
            <tr key={r.line_code} className={r.active ? "" : "admin-inactive"}>
              <td>{r.line_code}</td><td>{r.name}</td><td>{yesNo(r.auto_named)}</td><td>{r.sort_order}</td><td>{stateText(r.active)}</td>
              <td>
                <button type="button" className="admin-btn" onClick={() => setEditing(r)}>{at("edit")}</button>
                <button type="button" className="admin-btn" onClick={() => void patch(r.line_code, { active: !r.active })}>
                  {r.active ? at("deactivate") : at("activate")}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
