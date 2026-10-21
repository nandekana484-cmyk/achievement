// ライン画面の左のメニュー。
import { Link } from "react-router-dom";

type Props = { onTimetable: () => void; onLineEvents: () => void; onChangeOperator: () => void };

export function SideMenu({ onTimetable, onLineEvents, onChangeOperator }: Props) {
  return (
    <nav className="col-left" aria-label="メニュー">
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
