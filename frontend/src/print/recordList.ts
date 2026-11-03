// 印刷用の一覧の補助(React に依存しない)。完了日の表示と、開く先の URL。
import type { components } from "../api/schema";

export type RecordRow = components["schemas"]["RecordRowOut"];

/** 完了日時を「M/D HH:MM」にする(日本時間で書かれた ISO 文字列の、書かれたままの日付と時刻)。 */
export function completedText(iso: string): string {
  const m = /^\d{4}-(\d{2})-(\d{2})T(\d{2}:\d{2})/.exec(iso);
  return m ? `${Number(m[1])}/${Number(m[2])} ${m[3]}` : iso;
}

export function recordUrl(kittingNo: string, line?: string | null): string {
  return `/field/print/production-record/${encodeURIComponent(kittingNo)}${line ? `?line=${encodeURIComponent(line)}` : ""}`;
}

/** 面2が面1とつながっていないとき、紐づけの画面(その面2を選んだライン画面)へ行く URL。 */
export function linkScreenUrl(side2Line: string, side2KittingNo: string): string {
  return `/field/lines/${encodeURIComponent(side2Line)}?kitting_no=${encodeURIComponent(side2KittingNo)}`;
}

/** 一覧の絞り込みの条件を、API の query にする(空欄は送らない)。 */
export function filterQuery(f: { line: string; kitting: string; lot: string }): { line?: string; kitting_no?: string; lot_no?: string } {
  return {
    ...(f.line ? { line: f.line } : {}),
    ...(f.kitting.trim() ? { kitting_no: f.kitting.trim() } : {}),
    ...(f.lot.trim() ? { lot_no: f.lot.trim() } : {}),
  };
}

/** 一覧のラインの列: 面1と面2のライン(同じなら1つ)。 */
export function linesText(r: Pick<RecordRow, "side1_line" | "side2_line">): string {
  return [r.side1_line, r.side2_line].filter((x, i, a): x is string => !!x && a.indexOf(x) === i).join(" / ");
}
