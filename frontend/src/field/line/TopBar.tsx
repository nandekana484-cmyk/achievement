// ライン画面の上部: ライン名、稼働率、ラインの進捗率、今の担当者(押すと交代の画面)。
import type { Board } from "../../shared/api";
import { formatPercent } from "./steps";

type Props = { lineName: string; board: Board | null; onChangeOperator: () => void };

export function TopBar({ lineName, board, onChangeOperator }: Props) {
  const operator = board?.current_operator;
  return (
    <header className="kpi-bar">
      <span className="line-name">{lineName}</span>
      <Kpi label="稼働率" value={formatPercent(board?.utilization)} />
      <Kpi label="ラインの進捗率" value={formatPercent(board?.line_progress)} />
      <button type="button" className="kpi kpi-button" onClick={onChangeOperator} aria-label="担当者の交代">
        <span className="kpi-label">今の担当者(押すと交代)</span>
        <span className={`kpi-value${operator ? "" : " kpi-warn"}`}>{operator?.operator_name ?? "未設定"}</span>
      </button>
    </header>
  );
}

function Kpi({ label, value }: { label: string; value: string }) {
  return (
    <span className="kpi">
      <span className="kpi-label">{label}</span>
      <span className="kpi-value">{value}</span>
    </span>
  );
}
