// 左のカラムの上の、計画の検索欄。結果はキッティングNo.の単位で、当たったロットNo.や基板名も出す。押すとその計画を選ぶ。
// キッティングNo.が完全に一致する計画が1件だけなら、Enter でそのまま選ぶ(将来のバーコードリーダーのため)。
import { useEffect, useRef, useState } from "react";
import { api, type Plan, type SearchHit } from "../../shared/api";
import { exactKittingMatch } from "./planMatch";
import { formatMDHM } from "./timeScale";

type Props = { lineCode: string; onPick: (plan: Plan) => void };

const DEBOUNCE_MS = 300;

async function search(q: string, lineCode: string): Promise<SearchHit[] | null> {
  try {
    const { data } = await api.GET("/api/plans/search", { params: { query: { q, line_code: lineCode } } });
    return data ?? null;
  } catch {
    return null;
  }
}

export function PlanSearch({ lineCode, onPick }: Props) {
  const [q, setQ] = useState("");
  const [results, setResults] = useState<SearchHit[] | null>(null);
  const [failed, setFailed] = useState(false);
  const latest = useRef("");

  useEffect(() => {
    latest.current = q;
    if (!q.trim()) {
      setResults(null);
      return;
    }
    const timer = window.setTimeout(async () => {
      const found = await search(q, lineCode);
      if (latest.current !== q) return;
      setFailed(found === null);
      setResults(found ?? []);
    }, DEBOUNCE_MS);
    return () => window.clearTimeout(timer);
  }, [q, lineCode]);

  const pick = (plan: Plan) => {
    onPick(plan);
    setQ("");
    setResults(null);
  };

  const onEnter = async () => {
    const found = (await search(q, lineCode)) ?? [];
    const exact = exactKittingMatch(found.map((h) => h.plan), q);
    if (exact) pick(exact);
    else setResults(found);
  };

  return (
    <div className="plan-search">
      <input
        className="search-input"
        type="search"
        inputMode="text"
        placeholder="計画を検索"
        aria-label="計画を検索(キッティングNo.・ロットNo.・基板名)"
        value={q}
        onChange={(e) => setQ(e.target.value)}
        onKeyDown={(e) => e.key === "Enter" && void onEnter()}
      />
      {results && (
        <div className="search-results" role="listbox" aria-label="検索の結果">
          {failed && <p className="search-empty">通信できませんでした</p>}
          {!failed && results.length === 0 && <p className="search-empty">見つかりませんでした</p>}
          {results.map(({ plan: p, matched }) => (
            <button key={p.kitting_no} type="button" role="option" aria-selected={false} className="search-hit" onClick={() => pick(p)}>
              <span className="hit-kno">{p.kitting_no}</span>
              <span className="hit-name">
                {p.lots.length > 1 ? `${p.lots.length}ロット` : p.product_name}・計画数 {p.planned_qty}・{p.run_no}回目
              </span>
              <span className="hit-time">{p.planned_start ? `${formatMDHM(p.planned_start)}〜` : "日程なし"}</span>
              <span className="hit-matched">当たったところ: {matched.join("、")}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
