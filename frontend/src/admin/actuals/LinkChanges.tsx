// 「書き出し後に紐づけ・割り振りが変わった計画」: すでに書き出した計画の面1と面2の紐づけ、ロットへの割り振りが変わったもの。既存アプリの値は管理者が直す。
// 直したら「確認済み」にすると、一覧から消える。詳細: docs/design/actuals-export.md
import { useCallback, useEffect, useState } from "react";
import type { components } from "../../api/schema";
import { adminApi, useAdminCall } from "../adminApi";
import { at } from "../messages";

type Change = components["schemas"]["LinkChangeOut"];
const time = (iso: string) => iso.slice(0, 16).replace("T", " ");
const sourceText = (s: string) => at(s === "field" ? "links.source.field" : "links.source.admin");

export function LinkChanges({ refreshKey }: { refreshKey: unknown }) {
  const call = useAdminCall();
  const [rows, setRows] = useState<Change[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(() => {
    void call(() => adminApi.GET("/api/admin/actuals/link-changes")).then((r) => (r.ok ? setRows(r.data) : setError(r.message)));
  }, [call]);
  useEffect(load, [load, refreshKey]);

  const check = async (c: Change) => {
    const r = await call(() => adminApi.POST("/api/admin/actuals/link-changes/{change_id}/check", { params: { path: { change_id: c.id }, query: { kind: c.kind as "link" | "allocation" } } }));
    if (r.ok) load();
    else setError(r.message);
  };

  if (!rows || rows.length === 0) return error ? <p className="admin-error" role="alert">{error}</p> : null;
  return (
    <section className="actuals-links" aria-label={at("linkChanges.title")}>
      <h2>{at("linkChanges.title")}</h2>
      <p className="admin-note">{at("linkChanges.note")}</p>
      {error && <p className="admin-error" role="alert">{error}</p>}
      <table className="admin-table" aria-label={at("linkChanges.title")}>
        <thead>
          <tr>
            <th>{at("linkChanges.col.kind")}</th><th>{at("linkChanges.col.plan")}</th><th>{at("linkChanges.col.before")}</th><th>{at("linkChanges.col.after")}</th>
            <th>{at("linkChanges.col.by")}</th><th>{at("linkChanges.col.exported")}</th><th>{at("col.actions")}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((c) => (
            <tr key={`${c.kind}:${c.id}`}>
              <td>{at(c.kind === "allocation" ? "linkChanges.kind.allocation" : "linkChanges.kind.link")}</td>
              <td>{c.kind === "allocation" ? c.kitting_no : c.side2_kitting_no}</td>
              {c.kind === "allocation"
                ? <td colSpan={2}>{c.detail}</td>
                : <><td>{c.previous_partner ?? at("linkChanges.none")}</td><td>{c.action === "skip" ? at("links.state.unlinked") : (c.new_partner ?? at("linkChanges.none"))}</td></>}
              <td>{c.changed_by}({sourceText(c.source)}) {time(c.changed_at)}</td>
              <td>{time(c.exported_at)}</td>
              <td><button type="button" className="admin-btn" onClick={() => void check(c)}>{at("linkChanges.check")}</button></td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
