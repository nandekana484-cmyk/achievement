// 右のパネル: 選んだ計画の見出し、工程のボタン(押すたびに開始と終了が切り替わる)、NG数と備考。
import type { BoardPlan } from "../../shared/api";
import { STATE_TEXT, STEP_COLORS, STEP_ORDER, type StepStatus, formatPercent, stepStatus } from "./steps";

type Props = {
  plan: BoardPlan;
  isBusy: (key: string) => boolean;
  onStep: (status: StepStatus) => void;
  onNg: () => void;
  onRemark: () => void;
};

export const stepKey = (p: BoardPlan, step: string) => `step:${p.plan.kitting_no}|${p.plan.lot_no}:${step}`;

export function StepPanel({ plan, isBusy, onStep, onNg, onRemark }: Props) {
  const p = plan.plan;
  return (
    <section className="step-panel" aria-label="選んだ計画">
      <div className="plan-head">
        <div className="plan-title">
          <span className="plan-kno">{p.kitting_no}</span>
          {plan.completed && <span className="badge badge-done">完了</span>}
        </div>
        <div className="plan-name">{p.product_name}</div>
        <dl className="plan-facts">
          <Fact label="回" value={`${p.run_no}回目`} />
          <Fact label="計画数" value={`${p.planned_qty}`} />
          <Fact label="生産数の合計" value={`${plan.produced_qty}`} />
          <Fact label="進捗率" value={formatPercent(plan.progress)} />
          <Fact label="想定タクト" value={p.takt_sec === null ? "—" : `${p.takt_sec} 秒`} />
          <Fact label="NG数" value={plan.ng_qty === null ? "未入力" : `${plan.ng_qty}`} />
        </dl>
      </div>

      <div className="step-list">
        {STEP_ORDER.map((step) => {
          const s = stepStatus(plan.events, step);
          return (
            <button
              key={step}
              type="button"
              className={`step-button step-${s.state}`}
              style={{ borderLeftColor: STEP_COLORS[step] }}
              disabled={isBusy(stepKey(plan, step))}
              onClick={() => onStep(s)}
            >
              <span className="step-name">{s.label}</span>
              <span className={`step-state state-${s.state}`}>{STATE_TEXT[s.state]}</span>
              <span className="step-time">{s.timeText}</span>
              <span className="step-action">{isBusy(stepKey(plan, step)) ? "送信中…" : s.action === "start" ? "押すと開始" : "押すと終了"}</span>
            </button>
          );
        })}
      </div>

      <div className="input-row">
        <button type="button" className="btn" onClick={onNg} disabled={isBusy(`ng:${p.kitting_no}|${p.lot_no}`)}>
          NG数を入力
        </button>
        <button type="button" className="btn" onClick={onRemark} disabled={isBusy(`remark:${p.kitting_no}|${p.lot_no}`)}>
          備考を入力
        </button>
      </div>
    </section>
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
