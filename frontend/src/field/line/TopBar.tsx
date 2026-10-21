// ライン画面の上部: ライン名、稼働率、ラインの進捗率、今の担当者(押すと交代の画面)、表示言語の切り替え。
import { useI18n } from "../../i18n/I18nProvider";
import { LanguageSwitch } from "../../i18n/LanguageSwitch";
import type { Board } from "../../shared/api";
import { operatorLabel } from "./operatorLabel";
import { formatPercent } from "./steps";

type Props = { lineName: string; board: Board | null; onChangeOperator: () => void };

export function TopBar({ lineName, board, onChangeOperator }: Props) {
  const { t } = useI18n();
  const operator = board?.current_operator;
  return (
    <header className="kpi-bar">
      <span className="line-name">{lineName}</span>
      <Kpi label={t("topBar.utilization")} value={formatPercent(board?.utilization)} />
      <Kpi label={t("topBar.lineProgress")} value={formatPercent(board?.line_progress)} />
      <button type="button" className="kpi kpi-button" onClick={onChangeOperator} aria-label={t("topBar.operatorAria")}>
        <span className="kpi-label">{t("topBar.operatorLabel")}</span>
        <span className={`kpi-value${operator ? "" : " kpi-warn"}`}>
          {operator ? operatorLabel(operator.operator_name, operator.operator_worker_id, t) : t("topBar.operatorUnset")}
        </span>
      </button>
      <LanguageSwitch />
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
