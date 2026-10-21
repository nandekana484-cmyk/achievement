// ライン画面の左のメニュー。上に計画の検索欄を置く。
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { useI18n } from "../../i18n/I18nProvider";

type Props = { search: ReactNode; onTimetable: () => void; onLineEvents: () => void; onChangeOperator: () => void };

export function SideMenu({ search, onTimetable, onLineEvents, onChangeOperator }: Props) {
  const { t } = useI18n();
  return (
    <nav className="col-left" aria-label={t("sideMenu.aria")}>
      {search}
      <button type="button" className="menu-item" onClick={onTimetable}>
        {t("sideMenu.timetable")}
      </button>
      <button type="button" className="menu-item" onClick={onLineEvents}>
        {t("sideMenu.lineEvents")}
      </button>
      <button type="button" className="menu-item" onClick={onChangeOperator}>
        {t("sideMenu.changeOperator")}
      </button>
      <Link to="/field" className="menu-item menu-back">
        {t("sideMenu.backToLines")}
      </Link>
    </nav>
  );
}
