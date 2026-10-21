// 選んでいる計画(キッティングNo.)。board にあればそれを使い、無ければ(検索で選んだ表示範囲の外の計画)1件だけ読む。
// board を読み直すたびに読み直す。
import { useEffect, useState } from "react";
import { api, type Board, type BoardPlan } from "../../shared/api";

export function useSelectedPlan(board: Board | null, kittingNo: string | null): BoardPlan | null {
  const inBoard = kittingNo ? board?.plans.find((p) => p.plan.kitting_no === kittingNo) ?? null : null;
  const [extra, setExtra] = useState<BoardPlan | null>(null);

  useEffect(() => {
    if (!kittingNo || inBoard) {
      setExtra(null);
      return;
    }
    let alive = true;
    api
      .GET("/api/runs/{kitting_no}", { params: { path: { kitting_no: kittingNo } } })
      .then(({ data }) => alive && setExtra(data ?? null))
      .catch(() => undefined); // 読めなければ前の値のまま(次の読み直しでやり直す)
    return () => {
      alive = false;
    };
  }, [board, kittingNo, inBoard]);

  if (inBoard) return inBoard;
  return extra && extra.plan.kitting_no === kittingNo ? extra : null;
}
