// 選んでいる計画。board にあればそれを使い、無ければ(検索で選んだ表示範囲の外の計画)1件だけ読む。
// board を読み直すたびに読み直す。
import { useEffect, useState } from "react";
import { api, type Board, type BoardPlan } from "../../shared/api";

export type PlanRef = { kitting_no: string; lot_no: string };

export const refKey = (r: PlanRef) => `${r.kitting_no}|${r.lot_no}`;

export function useSelectedPlan(board: Board | null, selected: PlanRef | null): BoardPlan | null {
  const inBoard = selected ? board?.plans.find((p) => refKey(p.plan) === refKey(selected)) ?? null : null;
  const [extra, setExtra] = useState<BoardPlan | null>(null);

  useEffect(() => {
    if (!selected || inBoard) {
      setExtra(null);
      return;
    }
    let alive = true;
    api
      .GET("/api/runs/{kitting_no}/{lot_no}", { params: { path: selected } })
      .then(({ data }) => alive && setExtra(data ?? null))
      .catch(() => undefined); // 読めなければ前の値のまま(次の読み直しでやり直す)
    return () => {
      alive = false;
    };
  }, [board, selected, inBoard]);

  if (inBoard) return inBoard;
  return extra && selected && refKey(extra.plan) === refKey(selected) ? extra : null;
}
