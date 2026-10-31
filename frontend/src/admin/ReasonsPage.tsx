// 理由: 一覧、追加、名前・区分・入力の決まり・使い道・並び順の変更、無効化(消さない)。
import { type FormEvent, useState } from "react";
import { adminApi, type ReasonRow } from "./adminApi";
import { type AdminKey, at } from "./messages";
import { Check, Feedback, NumberInput, stateText, TextInput, useAdminList, useSave, yesNo } from "./parts";

const loadReasons = () => adminApi.GET("/api/admin/reasons");

type Flag = "requires_equipment" | "requires_text" | "usable_as_line_event" | "usable_as_restart";
const FLAGS: [Flag, AdminKey][] = [
  ["requires_equipment", "col.requiresEquipment"],
  ["requires_text", "col.requiresText"],
  ["usable_as_line_event", "col.lineEvent"],
  ["usable_as_restart", "col.restart"],
];  // counts_in_utilization は使わないので出さない(詳細: docs/design/metrics.md)
const CATEGORIES = ["loss", "non_loss"] as const;
const categoryText = (c: string) => at(c === "loss" ? "category.loss" : "category.non_loss");

const EMPTY = { name: "", name_vi: "", category: "loss", requires_equipment: false, requires_text: false,
  usable_as_line_event: true, usable_as_restart: false, counts_in_utilization: false };

function CategorySelect({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return (
    <select aria-label={at("col.category")} value={value} onChange={(e) => onChange(e.target.value)}>
      {CATEGORIES.map((c) => <option key={c} value={c}>{categoryText(c)}</option>)}
    </select>
  );
}

export function ReasonsPage() {
  const { rows, error, reload } = useAdminList<ReasonRow>(loadReasons);
  const { save, message } = useSave(reload);
  const [editing, setEditing] = useState<ReasonRow | null>(null);
  const [draft, setDraft] = useState(EMPTY);

  const add = async (e: FormEvent) => {
    e.preventDefault();
    if (await save(() => adminApi.POST("/api/admin/reasons", { body: { ...draft, name_vi: draft.name_vi || null } }))) setDraft(EMPTY);
  };
  const patch = (id: number, body: Partial<ReasonRow>) =>
    save(() => adminApi.PATCH("/api/admin/reasons/{reason_id}", { params: { path: { reason_id: id } }, body }));
  const saveEdit = async () => {
    if (!editing) return;
    const { id, active: _active, ...fields } = editing;
    if (await patch(id, { ...fields, name_vi: fields.name_vi || null })) setEditing(null);
  };

  return (
    <section aria-label={at("reasons.title")}>
      <h1>{at("reasons.title")}</h1>
      <p className="admin-note">{at("reasons.note")}</p>
      <Feedback message={message} error={error} />
      <form className="admin-add" onSubmit={add} aria-label={at("reasons.addTitle")}>
        <h2>{at("reasons.addTitle")}</h2>
        <TextInput label={at("col.name")} value={draft.name} onChange={(name) => setDraft({ ...draft, name })} required />
        <TextInput label={at("col.nameVi")} value={draft.name_vi} onChange={(name_vi) => setDraft({ ...draft, name_vi })} />
        <CategorySelect value={draft.category} onChange={(category) => setDraft({ ...draft, category })} />
        {FLAGS.map(([flag, key]) => (
          <label key={flag} className="admin-check"><Check label={at(key)} checked={draft[flag]} onChange={(v) => setDraft({ ...draft, [flag]: v })} />{at(key)}</label>
        ))}
        <button type="submit" className="admin-btn admin-primary">{at("add")}</button>
      </form>
      <table className="admin-table">
        <thead>
          <tr>
            <th>{at("col.name")}</th><th>{at("col.nameVi")}</th><th>{at("col.category")}</th>
            {FLAGS.map(([flag, key]) => <th key={flag} className="admin-flag">{at(key)}</th>)}
            <th>{at("col.sort")}</th><th>{at("col.state")}</th><th>{at("col.actions")}</th>
          </tr>
        </thead>
        <tbody>
          {rows?.map((r) => editing?.id === r.id ? (
            <tr key={r.id} className="admin-editing">
              <td><TextInput label={at("col.name")} value={editing.name} onChange={(name) => setEditing({ ...editing, name })} /></td>
              <td><TextInput label={at("col.nameVi")} value={editing.name_vi ?? ""} onChange={(name_vi) => setEditing({ ...editing, name_vi })} /></td>
              <td><CategorySelect value={editing.category} onChange={(category) => setEditing({ ...editing, category })} /></td>
              {FLAGS.map(([flag, key]) => (
                <td key={flag} className="admin-flag"><Check label={at(key)} checked={editing[flag]} onChange={(v) => setEditing({ ...editing, [flag]: v })} /></td>
              ))}
              <td><NumberInput label={at("col.sort")} value={editing.sort_order} onChange={(sort_order) => setEditing({ ...editing, sort_order })} /></td>
              <td>{stateText(r.active)}</td>
              <td>
                <button type="button" className="admin-btn admin-primary" onClick={() => void saveEdit()}>{at("save")}</button>
                <button type="button" className="admin-btn" onClick={() => setEditing(null)}>{at("cancel")}</button>
              </td>
            </tr>
          ) : (
            <tr key={r.id} className={r.active ? "" : "admin-inactive"}>
              <td>{r.name}</td><td>{r.name_vi ?? ""}</td><td>{categoryText(r.category)}</td>
              {FLAGS.map(([flag]) => <td key={flag} className="admin-flag">{yesNo(r[flag])}</td>)}
              <td>{r.sort_order}</td><td>{stateText(r.active)}</td>
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
