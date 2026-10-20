import { useParams } from "react-router-dom";

/**
 * ライン画面(開発指針 7.1)
 * 上部: 稼働率 / 進捗率 / 今の担当者
 * 左: メニュー、中央: タイムテーブル、右: 選んだ計画の工程ボタンと入力欄
 * 中身は次の段階で実装する。今はレイアウトの骨組みだけ。
 */
export function LineScreen() {
  const { lineCode } = useParams();

  return (
    <div className="line-screen">
      <header className="kpi-bar">
        <span className="line-name">{lineCode}ライン</span>
        <Kpi label="稼働率" value="—" />
        <Kpi label="進捗率" value="—" />
        <Kpi label="担当者" value="未設定" />
      </header>

      <nav className="col-left">
        <ul>
          <li>タイムテーブル</li>
          <li>付帯作業</li>
          <li>担当者の切替</li>
        </ul>
      </nav>

      <section className="col-center">
        <p className="placeholder">タイムテーブル(縦軸が時刻)</p>
      </section>

      <aside className="col-right">
        <p className="placeholder">計画を選ぶと、ここに工程ボタンが表示されます</p>
      </aside>
    </div>
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
