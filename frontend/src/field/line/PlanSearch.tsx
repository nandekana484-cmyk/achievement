// 左のカラムの上の、計画の検索欄。結果はキッティングNo.の単位で、当たったロットNo.や基板名も出す。押すとその計画を選ぶ。
// キッティングNo.が完全に一致する計画が1件だけなら、Enter でそのまま選ぶ(将来のバーコードリーダーのため)。
import { useEffect, useRef, useState } from "react";
import { useI18n } from "../../i18n/I18nProvider";
import { api, type Plan, type SearchHit } from "../../shared/api";
import { exactKittingMatch, plannedFrom, planSummary } from "./planMatch";

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
  const { t } = useI18n();
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
        placeholder={t("search.placeholder")}
        aria-label={t("search.aria")}
        value={q}
        onChange={(e) => setQ(e.target.value)}
        onKeyDown={(e) => e.key === "Enter" && void onEnter()}
      />
      {results && (
        <div className="search-results" role="listbox" aria-label={t("search.results")}>
          {failed && <p className="search-empty">{t("search.failed")}</p>}
          {!failed && results.length === 0 && <p className="search-empty">{t("search.empty")}</p>}
          {results.map(({ plan: p, matched }) => (
            <button key={p.kitting_no} type="button" role="option" aria-selected={false} className="search-hit" onClick={() => pick(p)}>
              <span className="hit-kno">{p.kitting_no}</span>
              <span className="hit-name">{planSummary(p, t)}</span>
              <span className="hit-time">{plannedFrom(p, t)}</span>
              <span className="hit-matched">{t("search.matched", { items: matched.join(t("common.listSeparator")) })}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
