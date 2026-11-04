// 識別票の部品: 見出しの出し方(日本語の下にベトナム語を小さく / 共通の見出しは「日本語 / ベトナム語」)、枠に収まる文字、縮尺。
import { type CSSProperties, Fragment } from "react";
import { fitFontPx, fitListFontPx, mmToPx } from "./fitText";
import { SLIP_TEXT, type SlipTextKey } from "./idSlipTexts";

/** 縮尺: A6(105mm × 148mm)いっぱいの様式を、余白 3mm を除いた大きさ(99mm × 142mm)に、比率を保って縮める(idslip.css の .slip-scale と同じ値)。 */
export const SLIP_SCALE = 0.94;

/** 日本語の下に、ベトナム語を小さい字で付ける(ベトナム語が無い見出しは日本語だけ)。 */
export function Bi({ k }: { k: SlipTextKey }) {
  const { ja, vi } = SLIP_TEXT[k];
  if (!vi) return <>{ja}</>;
  return <>{ja}<span className="slip-vi">{vi}</span></>;
}

/** 4種類で同じ見出し「日本語 / ベトナム語」(File № はベトナム語なし)。 */
export function Shared({ k }: { k: SlipTextKey }) {
  const { ja, vi } = SLIP_TEXT[k];
  return <>{ja}{vi && <span className="slip-vi-inline"> / {vi}</span>}</>;
}

type FitProps = { text: string; widthMm: number; heightMm: number; maxPx: number; maxLines?: number; className?: string; style?: CSSProperties };

/** 枠(widthMm × heightMm。縮める前の大きさ)に収まる大きさで文字を出す(最小 8px)。 */
export function Fit({ text, widthMm, heightMm, maxPx, maxLines, className = "", style }: FitProps) {
  const px = fitFontPx(text, { widthPx: mmToPx(widthMm), heightPx: mmToPx(heightMm), maxPx, maxLines });
  return <span className={`slip-fit ${className}`} style={{ fontSize: `${px}px`, ...style }} data-font-px={px}>{text}</span>;
}

type FitListProps = { items: string[]; widthMm: number; heightMm: number; maxPx: number; className?: string };

/** 項目を「, 」で並べ、枠に収まる大きさで出す(項目の途中では折り返さない。最小 8px)。 */
export function FitList({ items, widthMm, heightMm, maxPx, className = "" }: FitListProps) {
  const px = fitListFontPx(items, { widthPx: mmToPx(widthMm), heightPx: mmToPx(heightMm), maxPx });
  return (
    <span className={`slip-fit ${className}`} style={{ fontSize: `${px}px` }} data-font-px={px}>
      {items.map((item, i) => <Fragment key={`${item}:${i}`}><span className="slip-item">{item}{i < items.length - 1 ? "," : ""}</span>{" "}</Fragment>)}
    </span>
  );
}
