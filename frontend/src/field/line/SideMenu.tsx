// ライン画面の左のメニュー。上に計画の検索欄を置く。
import type { ReactNode } from "react";
import { Link } from "react-router-dom";

type Props = { search: ReactNode; onTimetable: () => void; onLineEvents: () => void; onChangeOperator: () => void };

export function SideMenu({ search, onTimetable, onLineEvents, onChangeOperator }: Props) {
  return (
    <nav className="col-left" aria-label="メニュー">
      {search}
      <button type="button" className="menu-item" onClick={onTimetable}>
        タイムテーブル
      </button>
      <button type="button" className="menu-item" onClick={onLineEvents}>
        付帯作業
      </button>
      <button type="button" className="menu-item" onClick={onChangeOperator}>
        担当者の交代
      </button>
      <Link to="/field" className="menu-item menu-back">
        ライン選択に戻る
      </Link>
    </nav>
  );
}
