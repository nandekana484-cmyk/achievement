// 実績の書き出しの一覧の表。生産数(累計)の欄だけ直せる。警告のある行は書き出さない(理由を出す)。
import { at } from "../messages";
import { type ActualsRow, type Edits, qtyOf, rowKey } from "./actuals";

type Props = {
  rows: ActualsRow[];
  drafts: Record<string, string>;
  edits: Edits;
  onDraft: (row: ActualsRow, text: string) => void;
};

export function ActualsTable({ rows, drafts, edits, onDraft }: Props) {
  return (
    <table className="admin-table actuals-table">
      <thead>
        <tr>
          <th>{at("actuals.col.kitting")}</th><th>{at("actuals.col.lot")}</th><th>{at("actuals.col.file")}</th>
          <th>{at("actuals.col.side")}</th><th>{at("actuals.col.product")}</th><th>{at("actuals.col.planned")}</th>
          <th>{at("actuals.col.produced")}</th><th>{at("actuals.col.ng1")}</th><th>{at("actuals.col.ng2")}</th>
          <th>{at("actuals.col.worker")}</th><th>{at("actuals.col.completed")}</th><th>{at("actuals.col.source")}</th>
          <th>{at("actuals.col.state")}</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => {
          const key = rowKey(r);
          const changed = qtyOf(r, edits) !== r.produced_qty;
          return (
            <tr key={key} className={r.exportable ? "" : "admin-inactive"}>
              <td>{r.kitting_no}</td><td>{r.lot_no}</td><td>{r.file_no}</td><td>{r.side}</td>
              <td>{r.product_name}</td><td>{r.planned_qty}</td>
              <td className={changed ? "actuals-changed" : ""}>
                <input className="admin-num" inputMode="numeric" aria-label={at("actuals.qtyLabel", { kitting: r.kitting_no, lot: r.lot_no })}
                  value={drafts[key] ?? String(r.produced_qty)} onChange={(e) => onDraft(r, e.target.value)} />
                <span className="actuals-total">{at("actuals.total", { total: r.kitting_produced_total })}</span>
              </td>
              <td>{r.ng_side1}</td><td>{r.ng_side2}</td>
              <td>{r.worker_id ? at("menu.user", { name: r.operator_name ?? "", id: r.worker_id }) : (r.operator_name ?? "")}</td>
              <td>{r.completed_on}</td><td>{r.source_db ?? ""}</td>
              <td>
                <strong>{r.exportable ? at("actuals.ok") : at("actuals.excluded")}</strong>
                {[...r.warnings, ...r.notes].map((w) => <div key={w} className={r.warnings.includes(w) ? "actuals-warning" : "actuals-noteline"}>{w}</div>)}
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
