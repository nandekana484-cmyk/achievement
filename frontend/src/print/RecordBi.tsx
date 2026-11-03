// 生産記録票の文言の出し方。日本語の下(または右)に、ベトナム語を小さい字で付ける(様式の sub-text)。
import { RECORD_TEXT, type RecordTextKey } from "./recordTexts";

export function Bi({ k, inline }: { k: RecordTextKey; inline?: boolean }) {
  const { ja, vi } = RECORD_TEXT[k];
  if (!vi) return <>{ja}</>;
  return <>{ja}{inline ? <span className="rec-sub-inline"> {vi}</span> : <span className="rec-sub">{vi}</span>}</>;
}

/** 「作業 / CÔNG VIỆC」の形(明細の見出し)。 */
export function Head({ k }: { k: RecordTextKey }) {
  const { ja, vi } = RECORD_TEXT[k];
  return <>{ja} / {vi}</>;
}
