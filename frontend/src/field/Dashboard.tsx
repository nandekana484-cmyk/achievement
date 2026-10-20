import { Link } from "react-router-dom";

// TODO: ラインの一覧はマスタAPIから取得する。今は仮のデータ。
const LINES = [{ code: "S", name: "Sライン" }];

export function Dashboard() {
  return (
    <main className="dashboard">
      <h1>生産ラインを選択</h1>
      <ul className="line-list">
        {LINES.map((l) => (
          <li key={l.code}>
            <Link to={`/field/lines/${l.code}`} className="line-card">
              {l.name}
            </Link>
          </li>
        ))}
      </ul>
    </main>
  );
}
