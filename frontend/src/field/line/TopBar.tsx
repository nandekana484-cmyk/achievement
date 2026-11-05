// ライン画面の上部: ライン名、今日の効率、今の担当者(押すと交代の画面)、表示言語の切り替え。
import { Link } from "react-router-dom";
import { useI18n } from "../../i18n/I18nProvider";
import { LanguageSwitch } from "../../i18n/LanguageSwitch";
import type { Board } from "../../shared/api";
import { formatPercent } from "../../shared/percent";
import { excludedCount } from "./metrics";
import { operatorLabel } from "./operatorLabel";

type Props = { lineCode: string; lineName: string; board: Board | null; onChangeOperator: () => void };

export function TopBar({ lineCode, lineName, board, onChangeOperator }: Props) {
  const { t } = useI18n();
  const operator = board?.current_operator;
  return (
    <header className="kpi-bar">
      <span className="line-name">{lineName}</span>
      <Kpi label={t("topBar.efficiency")} value={formatPercent(board?.efficiency.efficiency)}
        note={excludedCount(board) > 0 ? t("topBar.excluded", { count: excludedCount(board) }) : undefined} />
      <button type="button" className="kpi kpi-button" onClick={onChangeOperator} aria-label={t("topBar.operatorAria")}>
        <span className="kpi-label">{t("topBar.operatorLabel")}</span>
        <span className={`kpi-value${operator ? "" : " kpi-warn"}`}>
          {operator ? operatorLabel(operator.operator_name, operator.operator_worker_id, t) : t("topBar.operatorUnset")}
        </span>
      </button>
      <Link to={`/field/print/production-record?line=${encodeURIComponent(lineCode)}`} className="kpi record-link">{t("record.button")}</Link>
      <LanguageSwitch />
    </header>
  );
}

function Kpi({ label, value, note }: { label: string; value: string; note?: string }) {
  return (
    <span className="kpi">
      <span className="kpi-label">{label}</span>
      <span className="kpi-value">{value}</span>
      {note && <span className="kpi-note">{note}</span>}
    </span>
  );
}
