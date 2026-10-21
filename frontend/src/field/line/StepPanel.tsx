// 右のパネル: 選んだ計画(キッティングNo.)の見出しとロットの一覧、工程のボタン(押すたびに開始と終了が切り替わる)、NG数と備考。
import { useI18n } from "../../i18n/I18nProvider";
import type { BoardPlan } from "../../shared/api";
import { STATE_KEYS, STEP_COLORS, STEP_ORDER, type StepStatus, formatPercent, stepStatus } from "./steps";

type Props = {
  plan: BoardPlan;
  isBusy: (key: string) => boolean;
  onStep: (status: StepStatus) => void;
  onNg: () => void;
  onRemark: () => void;
};

export const stepKey = (p: BoardPlan, step: string) => `step:${p.plan.kitting_no}:${step}`;

export function StepPanel({ plan, isBusy, onStep, onNg, onRemark }: Props) {
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
        {p.warnings.length > 0 && <p className="plan-warning">{t("stepPanel.warnings", { items: p.warnings.join(" / ") })}</p>}
      </div>

      <div className="step-list">
        {STEP_ORDER.map((step) => {
          const s = stepStatus(plan.events, step, t);
          const busy = isBusy(stepKey(plan, step));
          return (
            <button key={step} type="button" className={`step-button step-${s.state}`} style={{ borderLeftColor: STEP_COLORS[step] }}
              disabled={busy} onClick={() => onStep(s)}>
              <span className="step-name">{s.label}</span>
              <span className={`step-state state-${s.state}`}>{t(STATE_KEYS[s.state])}</span>
              <span className="step-time">{s.timeText}</span>
              <span className="step-action">
                {busy ? t("common.sending") : s.action === "start" ? t("stepPanel.pressToStart") : t("stepPanel.pressToEnd")}
              </span>
            </button>
          );
        })}
      </div>

      <div className="input-row">
        <button type="button" className="btn" onClick={onNg}>{t("stepPanel.ngInput")}</button>
        <button type="button" className="btn" onClick={onRemark} disabled={isBusy(`remark:${p.kitting_no}`)}>{t("stepPanel.remarkInput")}</button>
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
