// 右のパネル: 選んだ計画(キッティングNo.)の見出しとロットの一覧、工程のボタン(押すたびに開始と終了が切り替わる)と
// 工程の行の「直す」、NG数と備考、押し忘れの追加と訂正の履歴。
import { useI18n } from "../../i18n/I18nProvider";
import type { BoardPlan, StepType } from "../../shared/api";
import { STATE_KEYS, STEP_COLORS, STEP_LABEL_KEYS, STEP_ORDER, type StepStatus, formatPercent, stepStatus } from "./steps";

type Props = {
  plan: BoardPlan;
  isBusy: (key: string) => boolean;
  onStep: (status: StepStatus) => void;
  onNg: () => void;
  onRemark: () => void;
  onFix: (step: StepType) => void;
  onAdd: () => void;
  onHistory: () => void;
};

export const stepKey = (p: BoardPlan, step: string) => `step:${p.plan.kitting_no}:${step}`;

const CANCEL_KEYS: Record<string, "stepPanel.cancelled.vanished" | "stepPanel.cancelled.reissued" | "stepPanel.cancelled.carried_over"> = {
  vanished: "stepPanel.cancelled.vanished",
  reissued: "stepPanel.cancelled.reissued",
  carried_over: "stepPanel.cancelled.carried_over",
};

export function StepPanel({ plan, isBusy, onStep, onNg, onRemark, onFix, onAdd, onHistory }: Props) {
  const { t } = useI18n();
  const p = plan.plan;
  return (
    <section className="step-panel" aria-label={t("stepPanel.aria")}>
      <div className="plan-head">
        <div className="plan-title">
          <span className="plan-kno">{p.kitting_no}</span>
          {plan.completed && <span className="badge badge-done">{t("common.done")}</span>}
        </div>
        <dl className="plan-facts">
          <Fact label={t("stepPanel.run")} value={t("unit.runNo", { run: p.run_no })} />
          <Fact label={t("stepPanel.plannedQty")} value={`${p.planned_qty}`} />
          <Fact label={t("stepPanel.producedQty")} value={`${plan.produced_qty}`} />
          <Fact label={t("stepPanel.progress")} value={formatPercent(plan.progress)} />
          <Fact label={t("stepPanel.takt")} value={p.takt_sec === null ? "—" : t("unit.seconds", { count: p.takt_sec })} />
          <Fact label={t("stepPanel.lots")} value={t("unit.lots", { count: p.lots.length })} />
        </dl>
        <LotTable plan={plan} />
        {p.is_stale && <p className="plan-warning">{t("stepPanel.stale")}</p>}
        {p.status === "cancelled" && <p className="plan-warning">{t(CANCEL_KEYS[p.cancel_reason ?? "vanished"] ?? "stepPanel.cancelled.vanished")}</p>}
        {p.warnings.length > 0 && <p className="plan-warning">{t("stepPanel.warnings", { items: p.warnings.join(" / ") })}</p>}
      </div>

      <div className="step-list">
        {STEP_ORDER.map((step) => {
          const s = stepStatus(plan.events, step, t);
          const busy = isBusy(stepKey(plan, step));
          return (
            <div key={step} className="step-row">
              <button type="button" className={`step-button step-${s.state}`} style={{ borderLeftColor: STEP_COLORS[step] }}
                disabled={busy} onClick={() => onStep(s)}>
                <span className="step-name">{s.label}</span>
                <span className={`step-state state-${s.state}`}>{t(STATE_KEYS[s.state])}</span>
                <span className="step-time">{s.timeText}</span>
                <span className="step-action">
                  {busy ? t("common.sending") : s.action === "start" ? t("stepPanel.pressToStart") : t("stepPanel.pressToEnd")}
                </span>
              </button>
              <button type="button" className="btn step-fix" disabled={s.records.length === 0}
                aria-label={t("stepPanel.fixAria", { step: t(STEP_LABEL_KEYS[step]) })} onClick={() => onFix(step)}>
                {t("stepPanel.fix")}
              </button>
            </div>
          );
        })}
      </div>

      <div className="input-row">
        <button type="button" className="btn" onClick={onNg}>{t("stepPanel.ngInput")}</button>
        <button type="button" className="btn" onClick={onRemark} disabled={isBusy(`remark:${p.kitting_no}`)}>{t("stepPanel.remarkInput")}</button>
        <button type="button" className="btn" onClick={onAdd}>{t("stepPanel.addForgotten")}</button>
        <button type="button" className="btn" onClick={onHistory}>{t("stepPanel.history")}</button>
      </div>
    </section>
  );
}

/** ロットの一覧(ロットNo.、基板名、数量)と、ロット・面ごとの最新のNG数。ロットが多いときはこの中でスクロールする。 */
function LotTable({ plan }: { plan: BoardPlan }) {
  const { t } = useI18n();
  const ngOf = (lot: string, side: number) => plan.ng_entries.find((n) => n.lot_no === lot && n.side === side)?.ng_qty;
  const sides = plan.plan.run_no === 2 ? [1, 2] : [1];
  return (
    <div className="lot-table-wrap">
      <table className="lot-table" aria-label={t("lotTable.aria")}>
        <thead>
          <tr>
            <th>{t("lotTable.lotNo")}</th>
            <th>{t("lotTable.productName")}</th>
            <th className="num">{t("lotTable.qty")}</th>
            {sides.map((s) => <th key={s} className="num">{t("lotTable.ngSide", { side: s })}</th>)}
          </tr>
        </thead>
        <tbody>
          {plan.plan.lots.map((lot) => (
            <tr key={lot.lot_no}>
              <td>{lot.lot_no}</td>
              <td>{lot.product_name}</td>
              <td className="num">{lot.planned_qty}</td>
              {sides.map((s) => <td key={s} className="num">{ngOf(lot.lot_no, s) ?? "—"}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div className="fact">
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}
