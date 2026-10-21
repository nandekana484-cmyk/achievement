// ダッシュボード: 生産ラインを選ぶ(ラインの一覧はマスタから読む)。
import { Link } from "react-router-dom";
import { Notice } from "../shared/Notice";
import { useMasters } from "../shared/useMasters";

export function Dashboard() {
  const { masters, error } = useMasters();
  return (
    <main className="dashboard">
      <h1>生産ラインを選択</h1>
      {error && <Notice kind="error">{error}</Notice>}
      {!masters && !error && <p className="placeholder">読み込み中…</p>}
      {masters && masters.lines.length === 0 && <Notice kind="info">ラインが登録されていません(計画の同期で自動登録されます)。</Notice>}
      <ul className="line-list">
        {masters?.lines.map((l) => (
          <li key={l.line_code}>
            <Link to={`/field/lines/${encodeURIComponent(l.line_code)}`} className="line-card">
              {l.name}
            </Link>
          </li>
        ))}
      </ul>
    </main>
  );
}
