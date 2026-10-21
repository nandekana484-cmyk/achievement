// 右のパネル: 選んだ計画(キッティングNo.)の見出しとロットの一覧、工程のボタン(押すたびに開始と終了が切り替わる)、NG数と備考。
import type { BoardPlan } from "../../shared/api";
import { STATE_TEXT, STEP_COLORS, STEP_ORDER, type StepStatus, formatPercent, stepStatus } from "./steps";

type Props = {
  plan: BoardPlan;
  isBusy: (key: string) => boolean;
  onStep: (status: StepStatus) => void;
  onNg: () => void;
  onRemark: () => void;
};

export const stepKey = (p: BoardPlan, step: string) => `step:${p.plan.kitting_no}:${step}`;

export function StepPanel({ plan, isBusy, onStep, onNg, onRemark }: Props) {
  const p = plan.plan;
  return (
    <section className="step-panel" aria-label="選んだ計画">
      <div className="plan-head">
        <div className="plan-title">
          <span className="plan-kno">{p.kitting_no}</span>
          {plan.completed && <span className="badge badge-done">完了</span>}
        </div>
        <dl className="plan-facts">
          <Fact label="回" value={`${p.run_no}回目`} />
          <Fact label="計画数(合計)" value={`${p.planned_qty}`} />
          <Fact label="生産数の合計" value={`${plan.produced_qty}`} />
          <Fact label="進捗率" value={formatPercent(plan.progress)} />
          <Fact label="想定タクト" value={p.takt_sec === null ? "—" : `${p.takt_sec} 秒`} />
          <Fact label="ロット" value={`${p.lots.length}ロット`} />
        </dl>
        <LotTable plan={plan} />
        {p.warnings.length > 0 && <p className="plan-warning">注意: {p.warnings.join(" / ")}</p>}
      </div>

      <div className="step-list">
        {STEP_ORDER.map((step) => {
          const s = stepStatus(plan.events, step);
          const busy = isBusy(stepKey(plan, step));
          return (
            <button key={step} type="button" className={`step-button step-${s.state}`} style={{ borderLeftColor: STEP_COLORS[step] }}
              disabled={busy} onClick={() => onStep(s)}>
              <span className="step-name">{s.label}</span>
              <span className={`step-state state-${s.state}`}>{STATE_TEXT[s.state]}</span>
              <span className="step-time">{s.timeText}</span>
              <span className="step-action">{busy ? "送信中…" : s.action === "start" ? "押すと開始" : "押すと終了"}</span>
            </button>
          );
        })}
      </div>

      <div className="input-row">
        <button type="button" className="btn" onClick={onNg}>NG数を入力</button>
        <button type="button" className="btn" onClick={onRemark} disabled={isBusy(`remark:${p.kitting_no}`)}>備考を入力</button>
      </div>
    </section>
  );
}

/** ロットの一覧(ロットNo.、基板名、数量)と、ロット・面ごとの最新のNG数。ロットが多いときはこの中でスクロールする。 */
function LotTable({ plan }: { plan: BoardPlan }) {
  const ngOf = (lot: string, side: number) => plan.ng_entries.find((n) => n.lot_no === lot && n.side === side)?.ng_qty;
  const sides = plan.plan.run_no === 2 ? [1, 2] : [1];
  return (
    <div className="lot-table-wrap">
      <table className="lot-table" aria-label="ロットの一覧">
        <thead>
          <tr>
            <th>ロットNo.</th>
            <th>基板名</th>
            <th className="num">数量</th>
            {sides.map((s) => <th key={s} className="num">NG 面{s}</th>)}
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
