// 識別票 4: バーコード照合用(幅105mm。高さの指定なし)。キッティングNo.ごとに1枚で、そのキッティングNo.の全ロットを並べる。
// 様式: docs/design/forms/id-4-barcode-check.html。A6縦(余白 3mm を除いた 99mm × 142mm)いっぱいに、行の高さの比率を保って広げ、文字も大きくする。
// ロットが多いときは、枠に収まるまで「Lot」の文字を縮める(最小 8px)。
import { Barcode } from "./Barcode";
import { barSize } from "./code39";
import type { IdSlip } from "./idSlipLogic";
import { Bi, Fit, FitList, Shared } from "./SlipParts";

const INNER_MM = 97.9; // カードの幅(99mm - 外枠)
const PAD_MM = 2.1; // 左右の余白 4px ずつ + 外枠の分
const COLS = [24, 18, 18, 40]; // 見出しの列は、ベトナム語を足したぶん様式(17/33/17/33)より広い。ロットが並ぶ「Lot」の欄を広く取る
const ROWS_MM = [15.8, 36.4, 24.3, 21.9, 42.5]; // 様式の行の高さの比率(28:60:40:36:70)で 140.9mm を分ける

const colMm = (pct: number) => (pct / 100) * INNER_MM - PAD_MM;

export function Slip4({ slip }: { slip: IdSlip }) {
  const bar = barSize(slip.kitting_no, INNER_MM - 8, 0.5);
  return (
    <div className="slip4" style={{ gridTemplateRows: ROWS_MM.map((h) => `${h}fr`).join(" ") }}>
      <div className="slip4-cell slip4-title"><Bi k="title4" /></div>
      <div className="slip4-row slip4-r2">
        <div className="slip4-cell slip4-lbl" style={{ width: `${COLS[0]}%` }}><span><Shared k="fileNo" /></span></div>
        <div className="slip4-cell slip4-val" style={{ width: `${COLS[1]}%` }}><Fit text={slip.file_no} widthMm={colMm(COLS[1])} heightMm={ROWS_MM[1] - 2} maxPx={27} maxLines={1} /></div>
        <div className="slip4-cell slip4-lbl" style={{ width: `${COLS[2]}%` }}><span><Shared k="lotNo" /></span></div>
        <div className="slip4-cell slip4-val slip4-lots" style={{ width: `${COLS[3]}%` }}><FitList items={slip.lots.map((l) => l.lot_no)} widthMm={colMm(COLS[3])} heightMm={ROWS_MM[1] - 2} maxPx={20} className="slip4-lotlist" /></div>
      </div>
      <div className="slip4-row slip4-r3">
        <div className="slip4-cell slip4-lbl" style={{ width: `${COLS[0]}%` }}><span><Shared k="productName" /></span></div>
        <div className="slip4-cell slip4-val" style={{ width: `${100 - COLS[0]}%` }}><Fit text={slip.product_name} widthMm={colMm(100 - COLS[0])} heightMm={ROWS_MM[2] - 2} maxPx={28} maxLines={2} /></div>
      </div>
      <div className="slip4-row slip4-r4">
        <div className="slip4-cell slip4-lbl slip4-lbl-long" style={{ width: `${COLS[0]}%` }}><span><Shared k="kittingNo" /></span></div>
        <div className="slip4-cell slip4-val" style={{ width: `${100 - COLS[0]}%` }}><Fit text={slip.kitting_no} widthMm={colMm(100 - COLS[0])} heightMm={ROWS_MM[3] - 2} maxPx={24} maxLines={1} /></div>
      </div>
      <div className="slip4-bar"><Barcode value={slip.kitting_no} barMm={bar.barMm} heightMm={24} /></div>
    </div>
  );
}
