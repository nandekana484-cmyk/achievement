// ライン画面の上: 表示する稼働日を選ぶ欄と「今日」のボタン、今日以外のときの「表示のみ」の帯。詳細: docs/design/line-screen.md
import { useI18n } from "../../i18n/I18nProvider";
import { dayBounds, isReadOnlyDay, isSelectableDay } from "./dayView";

type Props = { board: { date: string; today: string } | null; onChange: (day: string | null) => void };

export function DayPicker({ board, onChange }: Props) {
  const { t } = useI18n();
  const readOnly = isReadOnlyDay(board);
  const bounds = board ? dayBounds(board.today) : undefined;
  return (
    <>
      <div className="day-bar">
        <label className="day-label">
          <span>{t("dayPicker.label")}</span>
          <input
            type="date" className="day-input" aria-label={t("dayPicker.aria")} value={board?.date ?? ""} min={bounds?.min} max={bounds?.max} disabled={!board}
            onChange={(e) => {
              const v = e.target.value;
              if (!board || !isSelectableDay(v, board.today)) return; // 空・範囲の外は受けない
              onChange(v === board.today ? null : v);
            }}
          />
        </label>
        <button type="button" className="btn btn-small day-today" disabled={!board || !readOnly} onClick={() => onChange(null)}>{t("dayPicker.today")}</button>
      </div>
      {readOnly && <div className="day-readonly" role="status">{t("dayPicker.readOnly")}</div>}
    </>
  );
}
