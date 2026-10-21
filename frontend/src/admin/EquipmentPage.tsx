// 設備: 一覧、追加、名前(日本語・ベトナム語)と並び順の変更、無効化(消さない)。
import { type FormEvent, useState } from "react";
import { adminApi, type EquipmentRow, type LineRow } from "./adminApi";
import { at } from "./messages";
import { Feedback, NumberInput, stateText, TextInput, useAdminList, useSave } from "./parts";

const loadEquipment = () => adminApi.GET("/api/admin/equipment");
const loadLines = () => adminApi.GET("/api/admin/lines");

export function EquipmentPage() {
  const { rows, error, reload } = useAdminList<EquipmentRow>(loadEquipment);
  const { rows: lines } = useAdminList<LineRow>(loadLines);
  const { save, message } = useSave(reload);
  const [editing, setEditing] = useState<EquipmentRow | null>(null);
  const [draft, setDraft] = useState({ line_code: "", name: "", name_vi: "" });

  const add = async (e: FormEvent) => {
    e.preventDefault();
    const lineCode = draft.line_code || lines?.[0]?.line_code || "";
    const ok = await save(() => adminApi.POST("/api/admin/equipment", {
      body: { line_code: lineCode, name: draft.name, name_vi: draft.name_vi || null },
    }));
    if (ok) setDraft({ line_code: lineCode, name: "", name_vi: "" });
  };
  const patch = (id: number, body: Partial<EquipmentRow>) =>
    save(() => adminApi.PATCH("/api/admin/equipment/{equipment_id}", { params: { path: { equipment_id: id } }, body }));
  const saveEdit = async () => {
    if (editing && (await patch(editing.id, { name: editing.name, name_vi: editing.name_vi || null, sort_order: editing.sort_order }))) {
      setEditing(null);
    }
  };

  return (
    <section aria-label={at("equipment.title")}>
      <h1>{at("equipment.title")}</h1>
      <p className="admin-note">{at("equipment.note")}</p>
      <Feedback message={message} error={error} />
      <form className="admin-add" onSubmit={add} aria-label={at("equipment.addTitle")}>
        <h2>{at("equipment.addTitle")}</h2>
        <select aria-label={at("col.line")} value={draft.line_code} onChange={(e) => setDraft({ ...draft, line_code: e.target.value })}>
          {lines?.map((l) => <option key={l.line_code} value={l.line_code}>{at("lineOption", { name: l.name, code: l.line_code })}</option>)}
        </select>
        <TextInput label={at("col.name")} value={draft.name} onChange={(name) => setDraft({ ...draft, name })} required />
        <TextInput label={at("col.nameVi")} value={draft.name_vi} onChange={(name_vi) => setDraft({ ...draft, name_vi })} />
        <button type="submit" className="admin-btn admin-primary">{at("add")}</button>
      </form>
      <table className="admin-table">
        <thead>
          <tr>
            <th>{at("col.line")}</th><th>{at("col.name")}</th><th>{at("col.nameVi")}</th>
            <th>{at("col.sort")}</th><th>{at("col.state")}</th><th>{at("col.actions")}</th>
          </tr>
        </thead>
        <tbody>
          {rows?.map((r) => editing?.id === r.id ? (
            <tr key={r.id} className="admin-editing">
              <td>{r.line_code}</td>
              <td><TextInput label={at("col.name")} value={editing.name} onChange={(name) => setEditing({ ...editing, name })} /></td>
              <td><TextInput label={at("col.nameVi")} value={editing.name_vi ?? ""} onChange={(name_vi) => setEditing({ ...editing, name_vi })} /></td>
              <td><NumberInput label={at("col.sort")} value={editing.sort_order} onChange={(sort_order) => setEditing({ ...editing, sort_order })} /></td>
              <td>{stateText(r.active)}</td>
              <td>
                <button type="button" className="admin-btn admin-primary" onClick={() => void saveEdit()}>{at("save")}</button>
                <button type="button" className="admin-btn" onClick={() => setEditing(null)}>{at("cancel")}</button>
              </td>
            </tr>
          ) : (
            <tr key={r.id} className={r.active ? "" : "admin-inactive"}>
              <td>{r.line_code}</td><td>{r.name}</td><td>{r.name_vi ?? ""}</td><td>{r.sort_order}</td><td>{stateText(r.active)}</td>
              <td>
                <button type="button" className="admin-btn" onClick={() => setEditing(r)}>{at("edit")}</button>
                <button type="button" className="admin-btn" onClick={() => void patch(r.id, { active: !r.active })}>
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
