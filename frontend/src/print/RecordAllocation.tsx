// 生産記録票の印刷のページの「割り振り」(印刷に出ない所)。ロットごとの計画数、今の割り振り、「差を引くロット」の選択。
// 保存の前に、書き出し済みなら確認を出す。保存したら、数量の欄がすぐ変わる(onChanged でシートを読み直す)。詳細: docs/design/actuals-export.md
import { useState } from "react";
import { useI18n } from "../i18n/I18nProvider";
import { api } from "../shared/api";
import { Dialog } from "../shared/Dialog";
import { failureMessage, sendWithRetry } from "../shared/send";
import { uuidv4 } from "../shared/uuid";
import { type Allocation, canSaveAllocation, sumOf, toQuantities } from "./allocationEdit";

type Props = { allocation: Allocation; onChanged: () => void };
type Ask = { lines: string[]; label: string; run: () => void };

export function RecordAllocation({ allocation, onChanged }: Props) {
  const { t } = useI18n();
  const kno = allocation.kitting_no;
  const [open, setOpen] = useState(false);
  const [drafts, setDrafts] = useState(() => allocation.lots.map((l) => String(l.qty)));
  const [balance, setBalance] = useState<string | null>(null);
  const [workerId, setWorkerId] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [ask, setAsk] = useState<Ask | null>(null);
  const sum = sumOf(drafts);
  const mismatch = sum !== allocation.total;

  const pick = async (lotNo: string) => {
    setBalance(lotNo);
    setError(null);
    const r = await sendWithRetry(() => api.GET("/api/runs/{kitting_no}/allocation", { params: { path: { kitting_no: kno }, query: { balance_lot_no: lotNo } } }));
    if (!r.ok) return setError(failureMessage(r, t));
    if (r.data.proposal_error) return setError(r.data.proposal_error);
    setDrafts(r.data.lots.map((l) => String(l.qty)));
  };

  const save = async () => {
    setAsk(null);
    const body = { request_id: uuidv4(), worker_id: workerId.trim(), quantities: toQuantities(allocation.lots, drafts) };
    const r = await sendWithRetry(() => api.PUT("/api/runs/{kitting_no}/allocation", { params: { path: { kitting_no: kno } }, body }));
    if (!r.ok) return setError(failureMessage(r, t));
    setError(null);
    onChanged();
  };
  const reset = async () => {
    setAsk(null);
    const body = { request_id: uuidv4(), worker_id: workerId.trim() };
    const r = await sendWithRetry(() => api.POST("/api/runs/{kitting_no}/allocation/reset", { params: { path: { kitting_no: kno } }, body }));
    if (!r.ok) return setError(failureMessage(r, t));
    setError(null);
    setBalance(null);
    setDrafts(r.data.lots.map((l) => String(l.qty)));
    onChanged();
  };
  /** 書き出し済みなら、保存の前に確認を出す(AD-19 の紐づけと同じ)。 */
  const confirmed = (lines: string[], label: string, run: () => void) => {
    const all = allocation.exported ? [...lines, t("record.alloc.exported")] : lines;
    if (all.length === 0) run();
    else setAsk({ lines: all, label, run });
  };

  return (
    <div className="record-alloc">
      <div className="record-alloc-bar">
        <button type="button" className="btn" aria-expanded={open} onClick={() => setOpen(!open)}>{t("record.alloc.button")}</button>
        {allocation.stale && <span className="record-flag" role="alert">{t("record.alloc.stale")}</span>}
        {allocation.saved && <span className="record-alloc-note">{t("record.alloc.saved")}</span>}
      </div>
      {open && (
        <div className="record-alloc-panel" role="group" aria-label={t("record.alloc.title")}>
          <p className="record-alloc-hint">{t("record.alloc.hint", { total: allocation.total, planned: allocation.planned_total })}</p>
          <table className="record-table record-alloc-table">
            <thead><tr><th>{t("record.alloc.colLot")}</th><th>{t("record.alloc.colPlanned")}</th><th>{t("record.alloc.colQty")}</th><th>{t("record.alloc.colBalance")}</th></tr></thead>
            <tbody>
              {allocation.lots.map((l, i) => (
                <tr key={l.lot_no}>
                  <td>{l.lot_no}</td><td>{l.planned_qty}</td>
                  <td><input inputMode="numeric" aria-label={`${t("record.alloc.colQty")} ${l.lot_no}`} value={drafts[i]}
                    onChange={(e) => { setBalance(null); setDrafts(drafts.map((d, j) => (j === i ? e.target.value : d))); }} /></td>
                  <td><input type="radio" name="balance-lot" aria-label={`${t("record.alloc.colBalance")} ${l.lot_no}`} checked={balance === l.lot_no} onChange={() => void pick(l.lot_no)} /></td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="record-alloc-sum">{t("record.alloc.sum", { sum: sum ?? "-", total: allocation.total })} {mismatch && <strong>{t("record.alloc.sumMismatch")}</strong>}</p>
          <div className="record-alloc-actions">
            <label>{t("record.alloc.workerId")} <input value={workerId} onChange={(e) => setWorkerId(e.target.value)} autoComplete="off" /></label>
            <button type="button" className="btn btn-primary" disabled={!canSaveAllocation(drafts, allocation.total, workerId)}
              onClick={() => confirmed([], t("record.alloc.save"), () => void save())}>{t("record.alloc.save")}</button>
            {allocation.saved && (
              <button type="button" className="btn" disabled={workerId.trim() === ""}
                onClick={() => confirmed([t("record.alloc.resetAsk")], t("record.alloc.reset"), () => void reset())}>{t("record.alloc.reset")}</button>
            )}
            <button type="button" className="btn" onClick={() => setOpen(false)}>{t("record.alloc.close")}</button>
          </div>
          {error && <p className="plan-warning" role="alert">{error}</p>}
        </div>
      )}
      {ask && (
        <Dialog title={t("record.alloc.confirmTitle")} onCancel={() => setAsk(null)} actions={<button type="button" className="btn btn-primary" onClick={ask.run}>{ask.label}</button>}>
          {ask.lines.map((l) => <p key={l} className="confirm-message">{l}</p>)}
        </Dialog>
      )}
    </div>
  );
}
