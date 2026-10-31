// ライン画面の上部: ライン名、今日の効率、生産中の計画ごとの進捗率、今の担当者(押すと交代の画面)、表示言語の切り替え。
import { useI18n } from "../../i18n/I18nProvider";
import { LanguageSwitch } from "../../i18n/LanguageSwitch";
import type { Board } from "../../shared/api";
import { excludedCount, progressItems } from "./metrics";
import { operatorLabel } from "./operatorLabel";
import { formatPercent } from "./steps";

type Props = { lineName: string; board: Board | null; onChangeOperator: () => void };

export function TopBar({ lineName, board, onChangeOperator }: Props) {
  const { t } = useI18n();
  const operator = board?.current_operator;
  return (
    <header className="kpi-bar">
      <span className="line-name">{lineName}</span>
      <Kpi label={t("topBar.efficiency")} value={formatPercent(board?.efficiency.efficiency)}
        note={excludedCount(board) > 0 ? t("topBar.excluded", { count: excludedCount(board) }) : undefined} />
      {board && progressItems(board.plans).length > 0 && (
        <span className="kpi kpi-progress">
          <span className="kpi-label">{t("topBar.progress")}</span>
          <span className="progress-list">
            {progressItems(board.plans).map((p) => (
              <span key={p.kittingNo} className={`progress-chip${p.over ? " progress-over" : ""}`}>
                {p.kittingNo} <strong>{p.text}</strong>
              </span>
            ))}
          </span>
        </span>
      )}
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

function Kpi({ label, value, note }: { label: string; value: string; note?: string }) {
  return (
    <span className="kpi">
      <span className="kpi-label">{label}</span>
      <span className="kpi-value">{value}</span>
      {note && <span className="kpi-note">{note}</span>}
    </span>
  );
}
